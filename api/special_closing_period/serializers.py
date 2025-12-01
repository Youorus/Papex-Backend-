# serializers/special_closing_period.py

from rest_framework import serializers
from .models import SpecialClosingPeriod


class SpecialClosingPeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpecialClosingPeriod
        fields = ["id", "label", "start_datetime", "end_datetime"]

    def validate(self, attrs):
        start = attrs.get("start_datetime")
        end = attrs.get("end_datetime")
        if start and end and end < start:
            raise serializers.ValidationError(
                "La date et heure de fin doivent être postérieures ou égales au début."
            )
        return attrs