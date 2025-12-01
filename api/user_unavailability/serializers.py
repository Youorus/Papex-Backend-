from rest_framework import serializers

from .models import UserUnavailability


class UserUnavailabilitySerializer(serializers.ModelSerializer):
    user_display = serializers.StringRelatedField(source="user", read_only=True)

    class Meta:
        model = UserUnavailability
        fields = [
            "id",
            "user",
            "user_display",
            "start_date",
            "end_date",
            "label",
            "created_at",
        ]
        read_only_fields = ["created_at"]
