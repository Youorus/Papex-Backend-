# api/services/serializers.py
from rest_framework import serializers
from api.services.models import Service
from api.services.utils import code_from_label


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ["id", "code", "label", "price"]
        read_only_fields = ["id"]

    def validate_code(self, value):
        return code_from_label(value)

    def create(self, validated_data):
        if not validated_data.get("code"):
            validated_data["code"] = code_from_label(validated_data["label"])
        else:
            validated_data["code"] = code_from_label(validated_data["code"])
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if "code" in validated_data:
            validated_data["code"] = code_from_label(validated_data["code"])
        return super().update(instance, validated_data)