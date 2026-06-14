"""API routing for route planner app"""
from django.urls import path
from route_planner.views import GetGeocode, FuelStops


urlpatterns = [
    path('geocode/', GetGeocode.as_view()),
    path('fuel-stations/route/', FuelStops.as_view())
]