"""All the services related to the route planner"""
import requests
import logging
import httpx
import math
import polyline

from itertools import pairwise, islice
from typing import Tuple, List
from django.conf import settings
from django.core.cache import cache

from route_planner.models import FuelStop
from fuel_stops.cache import generate_cache_key


logger = logging.getLogger(__name__)


async def geocode(query: str) -> Tuple[str, str]:
    """get geocodes for the location"""

    cache_key = generate_cache_key("polyline", query)
    cached = cache.get(cache_key)
    if cached:
        logger.debug("Cache hit: polyline")
        return cached
    
    geocode_url = "https://geocode.maps.co/search"
    params = {
        "api_key": settings.GEO_CODER_API_KEY,
        "q": query
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                geocode_url, params=params
            )
            data = response.json()
    except Exception as exec:
        logger.error(exec, f"failed to fetch geocode for {query}")
        return None, None
    
    if not data:
        return None, None
    latitude = data[0]["lat"]
    longitude = data[0]["lon"]

    cache.set(cache_key, (longitude, latitude), timeout=60*60*24)
    return longitude, latitude


class RoutingService:
    """All methods related to routing logic comes here"""
    TARGET_POLYLINE_POINTS = 200

    start_point: List[float] = []
    end_point: List[float] = []
    route_polyline: List[List[float]] = []
    route_stations: list = []
    total_route_distance: float  # miles

    
    def __init__(self, start_point, end_point):
        self.start_point = start_point
        self.end_point = end_point
        self.route_polyline, self.total_route_distance = self.get_route_polyline()
        self.route_stations = self.route_position(
            self.find_stations_along_route()
        )

    def get_route_polyline(self):
        route_api = "https://api.openrouteservice.org/v2/directions/driving-hgv"

        headers = {
            "Authorization": settings.ROUTE_API_KEY,
            "Content-Type": "application/json"
        }

        payload = {
            "coordinates": [self.start_point, self.end_point],
            "instructions": False,
            "geometry_simplify": True
        }


        try:
            response = requests.post(
                route_api, json=payload, headers=headers
            )
            data = response.json()
        except Exception as exec:
            logger.error(
                exec, 
                f"failed to get route for {self.start_point} - {self.end_point}"
            )
            return None, None
        try:
            compressed_polyline = data["routes"][0]["geometry"]
            total_distance = data["routes"][0]['summary']['distance'] / 1609.344
        except (KeyError, IndexError, TypeError) as exec:
            logger.error(
                exec, 
                f"failed to parse route data for {self.start_point} - {self.end_point}"
            )
            return None, None
        
        decoded = polyline.decode(compressed_polyline)
        step = max(1, len(decoded) // self.TARGET_POLYLINE_POINTS)
        lats, lons = zip(*islice(decoded, 0, None, step))
        clean_polyline = list(zip(lons, lats))
        return clean_polyline, total_distance
    
    def get_bbox(self, radius_miles):
        longitudes, latitudes = zip(*self.route_polyline)
        delta = radius_miles / 111  # 1 degree ≈ 111 mile
        return (min(longitudes) - delta, max(longitudes) + delta,
                 min(latitudes) - delta, max(latitudes) + delta)

    def find_stations_along_route(self, radius_km=5):
        min_lon, max_lon, min_lat, max_lat = self.get_bbox(
            radius_km
        )

        relevant_fuel_stops = FuelStop.objects.filter(
            latitude__range=(min_lat, max_lat),
            longitude__range=(min_lon, max_lon)
        ).only('name', 'latitude', 'longitude', 'fuel_price')
        route_stations_data = {}

        for station in relevant_fuel_stops:
            min_distance_data = self.min_distance_to_polyline(station)
            min_distance_to_polyline = min_distance_data.get('distance_to_polyline')
            if (
                min_distance_to_polyline and
                min_distance_to_polyline <= radius_km
            ):
                route_stations_data[
                    f"{min_distance_data['segment_start']}-{min_distance_data['segment_end']}"
                ] = min_distance_data
        return route_stations_data
    
    @staticmethod
    def haversine(lon1, lat1, lon2, lat2):
        R = 3959 # radius of earth in miles
        dlon, dlat = math.radians(lon2-lon1), math.radians(lat2-lat1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    def point_to_segment_distance(
            self, fuel_station_geocode, 
            segment_start, segment_end
        ):
        lon, lat = fuel_station_geocode
        alon, alat, blon, blat = segment_start[0], segment_start[1], segment_end[0], segment_end[1]
        delta_lon, delta_lat = blon-alon, blat-alat
        projection_ratio = max(
            0, min(1, ((lon-alon)*delta_lon) +(lat-alat)*delta_lat / 
                   (delta_lon**2 + delta_lat**2))
        )
        return self.haversine(
            lon, lat, 
            alon + projection_ratio*delta_lon, 
            alat + projection_ratio*delta_lat
        )

    def min_distance_to_polyline(
            self, station, distance_to_polyline=float('inf')
        ):
        near_segment_data = {}
        for segment_start, segment_end in pairwise(self.route_polyline):
            if (
                abs(segment_start[1] - station.latitude) > 0.5 or
                abs(segment_start[0] - station.longitude) > 0.7
            ):
                # avoids segments more than 35 miles away
                continue
            _distance_to_polyline = self.point_to_segment_distance(
                (station.longitude, station.latitude),
                segment_start, segment_end
            )
            if _distance_to_polyline < distance_to_polyline:
                distance_to_polyline = _distance_to_polyline
                near_segment_data = {
                    'segment_start': segment_start,
                    'segment_end': segment_end,
                    'distance_to_polyline': _distance_to_polyline,
                    'station':station
                }
        return near_segment_data
    
    def route_position(self, route_stations_data):
        cumulative = 0
        route_data = []
        for segment_start, segment_end in pairwise(self.route_polyline):
            segment_len = self.haversine(*segment_start, *segment_end)
            cumulative += segment_len
            try:
                station_data = route_stations_data[
                    f"{segment_start}-{segment_end}"
                ]
            except KeyError:
                # No station near segment found
                continue
            station = station_data['station']
            route_data.append(
                {"segment_start": segment_start,
                 "segment_end": segment_end,
                 "covered_distance": cumulative,
                 "station_name": station.name,
                 "station_geocode": [station.longitude, station.latitude],
                 "fuel_price": station.fuel_price,
                 "segment_to_station": station_data['distance_to_polyline']}
            )
        return route_data
    

class FuelCostOptimizer:
    """
    All the methods and properties for calculating 
    the fuel cost optimized route.
    """

    truck_range: float = 500.0  # miles
    mileage: float = 10.0  # mpg
    tank_capacity: float
    route_data: List[dict]
    total_route_distance: float

    def __init__(
            self, route_data, total_route_distance,
            truck_range=None, mileage=None
        ):
        if truck_range is not None:
            self.truck_range = truck_range
        if mileage is not None:
            self.mileage = mileage
        self.tank_capacity = self.truck_range / self.mileage  # gallons
        self.route_data = route_data
        self.total_route_distance = total_route_distance
        self.optimal_fuel_stops_data = self.prepare_data(
            *self.find_optimal_fuel_stops()
        )

    def find_optimal_fuel_stops(self):
        route_start = {
            'station_name': 'Start', 'covered_distance': 0.0, 
            'fuel_price': 0.0
        }
        route_end = {
            'station_name': 'Destination', 
            'covered_distance': self.total_route_distance, 
            'fuel_price': 0.0
        }
        all_nodes = [route_start] + self.route_data + [route_end]

        total_nodes = len(all_nodes)
        max_cost = float('inf')

        cheapest_cost_to_reach = [max_cost] * total_nodes
        came_from = [-1] * total_nodes
        cheapest_cost_to_reach[0] = 0.0

        for current_node_index in range(1, total_nodes):
            for previous_node_index in range(current_node_index):
                if cheapest_cost_to_reach[previous_node_index] == max_cost:
                    continue

                miles_between = (all_nodes[current_node_index]['covered_distance']
                                - all_nodes[previous_node_index]['covered_distance'])

                if miles_between > self.truck_range:
                    continue

                gallons_needed = miles_between / self.mileage
                cost_from_prev = (
                    cheapest_cost_to_reach[previous_node_index]
                    + gallons_needed * all_nodes[previous_node_index]['fuel_price']
                )

                if cost_from_prev < cheapest_cost_to_reach[current_node_index]:
                    cheapest_cost_to_reach[current_node_index] = cost_from_prev
                    came_from[current_node_index] = previous_node_index

        if cheapest_cost_to_reach[-1] == max_cost:
            logger.error('Route not feasible — gap between stations exceeds max range.')
            return None

        path_indices = []
        node_index = total_nodes - 1
        while node_index != -1:
            path_indices.append(node_index)
            node_index = came_from[node_index]
        path_indices.reverse()
        return all_nodes, path_indices

    def prepare_data(self, all_nodes, path_indices):
        optimal_stops = []
        leg_details = []
        total_cost = 0.0
        total_gallons = 0.0

        for step in range(len(path_indices) - 1):
            from_node = all_nodes[path_indices[step]]
            to_node = all_nodes[path_indices[step + 1]]

            miles_this_leg = to_node['covered_distance'] - from_node['covered_distance']
            gallons_purchased = miles_this_leg / self.mileage
            leg_cost = gallons_purchased * from_node['fuel_price']

            total_cost += leg_cost
            total_gallons += gallons_purchased

            is_real_station = step > 0  # skip virtual start
            if is_real_station:
                optimal_stops.append(from_node)

            leg_details.append({
                'from':               from_node['station_name'],
                'to':                 to_node['station_name'],
                'miles':              round(miles_this_leg, 1),
                'gallons_purchased':  round(gallons_purchased, 2),
                'price_per_gallon':   round(from_node['fuel_price'], 3),
                'leg_cost_usd':       round(leg_cost, 2),
            })

        return {
            'optimal_stops': optimal_stops,
            'leg_details':   leg_details,
            'total_cost_usd':   round(total_cost, 2),
            'total_gallons':    round(total_gallons, 2),
            'number_of_stops':  len(optimal_stops),
            'total_distance': round(self.total_route_distance, 1)
        }
