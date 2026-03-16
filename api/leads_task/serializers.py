"""
api/leads_task/serializers.py

Serializer DRF pour les tâches liées aux leads.
"""

from rest_framework import serializers

from .models import LeadTask


class LeadTaskSerializer(serializers.ModelSerializer):
    """
    Serializer principal pour les tâches de leads.

    Expose les labels des relations pour simplifier le frontend.
    """

    task_type_label = serializers.CharField(
        source="task_type.label",
        read_only=True,
    )

    status_label = serializers.CharField(
        source="status.label",
        read_only=True,
    )

    assigned_to_name = serializers.CharField(
        source="assigned_to.get_full_name",
        read_only=True,
    )

    class Meta:
        model = LeadTask

        fields = [
            "id",

            "lead",

            "task_type",
            "task_type_label",

            "status",
            "status_label",

            "title",
            "description",

            "due_at",
            "created_at",
            "completed_at",

            "assigned_to",
            "assigned_to_name",

            "created_by",

            "reschedule_count",
            "reschedule_history",

            "metadata",
        ]

        read_only_fields = [
            "id",
            "created_at",
            "completed_at",
            "reschedule_count",
            "reschedule_history",
        ]