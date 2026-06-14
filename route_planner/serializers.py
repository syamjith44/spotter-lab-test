"""serializers and validators for route planner APIs"""
import re

from rest_framework import serializers


class GetGeoCodeSerializer(serializers.Serializer):
    start_point = serializers.CharField(required=True)
    end_point = serializers.CharField(required=True)

    def validate(self, attrs):
        pattern = r'[^a-zA-Z0-9]+'
        attrs['start_point'] = re.sub(pattern, '+', attrs['start_point'])
        attrs['end_point'] = re.sub(pattern, '+', attrs['end_point'])
        return super().validate(attrs)
    

class GetFuelStopsSerializer(serializers.Serializer):
    start_point = serializers.ListField(
        child=serializers.FloatField(required=True), 
        required=True, allow_empty=False, allow_null=False
    )
    end_point = serializers.ListField(
        child=serializers.FloatField(required=True), 
        required=True, allow_empty=False, allow_null=False
    )
