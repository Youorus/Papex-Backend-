from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import JuristAppointment

User = get_user_model()


class JuristSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "first_name", "last_name", "email"]


class LeadMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()  # OU ton modèle Client/Lead selon ta structure
        fields = ["id", "first_name", "last_name", "email"]


class JuristAppointmentSerializer(serializers.ModelSerializer):
    jurist = JuristSerializer(read_only=True)
    lead = LeadMiniSerializer(read_only=True)

    class Meta:
        model = JuristAppointment
        fields = "__all__"


class JuristAppointmentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = JuristAppointment
        fields = ["lead", "jurist", "date"]

    def validate(self, data):
        lead = data["lead"]
        jurist = data["jurist"]
        date = data["date"]

        # Vérif: le juriste n’a pas déjà un RDV à ce créneau précis
        if JuristAppointment.objects.filter(jurist=jurist, date=date).exists():
            raise serializers.ValidationError(
                {
                    "non_field_errors": [
                        "Impossible de réserver ce créneau, il est déjà pris."
                    ]
                }
            )

        # Vérif: le lead n’a pas déjà un RDV ce jour-là (tous juristes confondus)
        if JuristAppointment.objects.filter(lead=lead, date__date=date.date()).exists():
            raise serializers.ValidationError(
                {
                    "non_field_errors": [
                        "Ce lead a déjà un rendez-vous juriste ce jour-là."
                    ]
                }
            )

        return data
