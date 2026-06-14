"""All the route planner APIs"""
import asyncio

from rest_framework.views import APIView, Response, status
from asgiref.sync import async_to_sync

from route_planner.serializers import GetGeoCodeSerializer, GetFuelStopsSerializer
from route_planner.services import geocode, RoutingService, FuelCostOptimizer


class GetGeocode(APIView):
    """
    API to get the geocodes for the the 
    text based locations.
    """

    def post(self, request):
        serializer = GetGeoCodeSerializer(
            data=request.data
        )
        if not serializer.is_valid():
            return Response(
                serializer.errors, 
                status=status.HTTP_400_BAD_REQUEST
            )
        data = serializer.data
        async def fetch_all_geocodes():
            tasks = [geocode(value) for value in data.values()]
            return await asyncio.gather(*tasks)

        keys = list(data.keys())
        # tasks = [geocode(value) for value in data.values()]
        # results = await asyncio.gather(*tasks)
        results = async_to_sync(fetch_all_geocodes)()
        response_data = {
            key: result 
            for key, result in zip(keys, results)
        }
        return Response(
            response_data, 
            status=status.HTTP_200_OK
        )
    

class FuelStops(APIView):
    """
    API to get the best fuel stops along the route.
    """

    def post(self, request):
        serializer = GetFuelStopsSerializer(
            data=request.data
        )
        if not serializer.is_valid():
            return Response(
                serializer.errors, 
                status=status.HTTP_400_BAD_REQUEST
            )
        data = serializer.data
        fuel_stop_router = RoutingService(
            data['start_point'], data['end_point']
        )
        fuel_cost_optimizer = FuelCostOptimizer(
            route_data=fuel_stop_router.route_stations,
            total_route_distance=fuel_stop_router.total_route_distance
        )
        return Response(
            {
                'fuel_plan': fuel_cost_optimizer.optimal_fuel_stops_data,
                'polyline':  fuel_stop_router.route_polyline
            },
            status=status.HTTP_200_OK
        )
