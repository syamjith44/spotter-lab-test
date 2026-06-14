"""Command to add the fuel stations data to the db"""
import csv
import logging
from asgiref.sync import async_to_sync
from django.core.management import BaseCommand

from route_planner.services import geocode
from route_planner.models import FuelStop


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Adds fuel stations in bulk and geocodes them.
    """

    def handle(self, *args, **kwargs):
        with open('data/fuel-prices-for-be-assessment.csv') as f:
            reader = csv.DictReader(f)
            counter = 1
            for row in reader:
                if counter < 1742:
                    counter += 1
                    continue
                query = f"{row['Address'].split(',')[0]}+{row['City']}+{row['State']}"
                longitude, latitude = async_to_sync(geocode)(query)
                if not (latitude and longitude):
                    logger.error(
                        f"{row['OPIS Truckstop ID']} - "
                        f"{row['Truckstop Name']} - could not geocode"
                    )
                else:
                    logger.info(f"{counter}: {latitude}, {longitude}")
                FuelStop.objects.create(
                    name=row['Truckstop Name'],
                    address=row['Address'],
                    city=row['City'],
                    state=row['State'],
                    fuel_price=row['Retail Price'],
                    latitude=latitude,
                    longitude=longitude
                )
                counter += 1
