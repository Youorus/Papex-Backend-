"""
api/leads_task/serializers.py
"""

from rest_framework import serializers

from .models import LeadTask
from .constants import LeadTaskStatus


class LeadTaskSerializer(serializers.ModelSerializer):
    """
    Serializer principal pour les tâches de leads.

    ✔ Expose labels + couleurs pour le frontend
    ✔ completed_at retiré des read_only_fields → le frontend peut le patcher
    """

    # ─────────────────────────────
    # Labels & helpers frontend
    # ─────────────────────────────
    task_type_label = serializers.CharField(
        source="task_type.label",
        read_only=True,
    )

    status_label = serializers.SerializerMethodField()
    status_color = serializers.SerializerMethodField()

    assigned_to_label = serializers.SerializerMethodField()

    is_overdue = serializers.BooleanField(read_only=True)

    # ─────────────────────────────
    # Méthodes
    # ─────────────────────────────
    def get_status_label(self, obj):
        return dict(LeadTaskStatus.CHOICES).get(obj.status, obj.status)

    def get_status_color(self, obj):
        return LeadTaskStatus.COLORS.get(obj.status, "default")

    def get_assigned_to_label(self, obj):
        if obj.assigned_to:
            return obj.assigned_to.get_full_name() or obj.assigned_to.username
        return None

    # ─────────────────────────────
    # Meta
    # ─────────────────────────────
    class Meta:
        model = LeadTask

        fields = [
            "id",
            "lead",
            "task_type",
            "task_type_label",
            "status",
            "status_label",
            "status_color",
            "title",
            "description",
            "due_at",
            "created_at",
            "completed_at",
            "assigned_to",
            "assigned_to_label",
            "created_by",
            "reschedule_count",
            "reschedule_history",
            "is_overdue",
            "metadata",
        ]

        read_only_fields = [
            "id",
            "created_at",
            # completed_at N'EST PAS read_only → le service frontend peut le patcher via complete()
            # reschedule_count et reschedule_history sont gérés côté modèle
            "reschedule_count",
            "reschedule_history",
        ]