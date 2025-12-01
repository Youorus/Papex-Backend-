# api/appointments/test_serializers.py

from django.utils import timezone
from rest_framework import serializers

from api.appointment.models import Appointment
from api.leads.serializers import LeadSerializer
from api.users.assigned_user_serializer import AssignedUserSerializer


class AppointmentSerializer(serializers.ModelSerializer):
    """
    Serializer principal du modèle Appointment.
    Inclut les données liées (lead, created_by) + gestion de l’ID lead à l’écriture.
    """

    # Lecture
    lead = LeadSerializer(read_only=True)
    created_by = AssignedUserSerializer(read_only=True)
    date_display = serializers.SerializerMethodField()

    # Écriture (IDs)
    lead_id = serializers.PrimaryKeyRelatedField(
        queryset=Appointment._meta.get_field("lead").related_model.objects.all(),
        source="lead",
        write_only=True,
        required=True,
    )

    class Meta:
        model = Appointment
        fields = [
            "id",
            "lead",
            "lead_id",
            "date",
            "date_display",
            "note",
            "created_by",
            "created_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "date_display", "lead"]

    def get_date_display(self, obj):
        return obj.date.strftime("%d/%m/%Y %H:%M") if obj.date else None

    def validate_date(self, value):
        """
        Vérifie que la date de RDV n’est pas dans le passé.
        """
        if value < timezone.now():
            raise serializers.ValidationError(
                "La date du rendez-vous ne peut pas être dans le passé."
            )
        return value

    def create(self, validated_data):
        user = self.context["request"].user
        validated_data["created_by"] = user
        return super().create(validated_data)
