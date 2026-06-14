"""All the route_planner related logic and database logic here"""
from django.db import models


class FuelStop(models.Model):
    """
    Fuel stop details including price, 
    latitude and longitude data.
    """
    name = models.CharField(max_length=100)
    latitude = models.FloatField(db_index=True, null=True)
    longitude = models.FloatField(db_index=True, null=True)
    address = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    fuel_price = models.FloatField(db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['latitude', 'longitude']),
        ]