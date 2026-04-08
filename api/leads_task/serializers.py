"""
api/leads_task/serializers.py
"""

from rest_framework import serializers

from .models import LeadTask, LeadTaskComment
from .constants import LeadTaskStatus, LeadTaskPriority


# ─────────────────────────────────────────────
# COMMENT SERIALIZER
# ─────────────────────────────────────────────

class LeadTaskCommentSerializer(serializers.ModelSerializer):

    author_label = serializers.SerializerMethodField()
    author_initials = serializers.SerializerMethodField()

    class Meta:
        model = LeadTaskComment
        fields = [
            "id",
            "task",
            "author",
            "author_label",
            "author_initials",
            "content",
            "created_at",
            "updated_at",
            "is_edited",
        ]
        read_only_fields = [
            "id",
            "author",
            "author_label",
            "author_initials",
            "created_at",
            "updated_at",
            "is_edited",
        ]

    def get_author_label(self, obj) -> str | None:
        if not obj.author:
            return None
        return f"{obj.author.first_name} {obj.author.last_name}".strip() or obj.author.email

    def get_author_initials(self, obj) -> str | None:
        if not obj.author:
            return None
        first = (obj.author.first_name or "")[:1].upper()
        last = (obj.author.last_name or "")[:1].upper()
        return f"{first}{last}" or obj.author.email[:2].upper()


# ─────────────────────────────────────────────
# TASK SERIALIZER
# ─────────────────────────────────────────────

class LeadTaskSerializer(serializers.ModelSerializer):

    # Labels lisibles
    status_label = serializers.SerializerMethodField()
    status_color = serializers.SerializerMethodField()
    priority_label = serializers.SerializerMethodField()
    priority_color = serializers.SerializerMethodField()
    task_type_label = serializers.SerializerMethodField()
    assigned_to_label = serializers.SerializerMethodField()
    created_by_label = serializers.SerializerMethodField()

    # Propriétés calculées
    is_overdue = serializers.SerializerMethodField()
    comment_count = serializers.SerializerMethodField()

    # Commentaires imbriqués (lecture seule, liste légère)
    comments = LeadTaskCommentSerializer(many=True, read_only=True)

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
            "priority",
            "priority_label",
            "priority_color",
            "title",
            "description",
            "due_at",
            # "estimated_duration", <-- SUPPRIMÉ
            # "tags",               <-- SUPPRIMÉ
            "created_at",
            "completed_at",
            "assigned_to",
            "assigned_to_label",
            "created_by",
            "created_by_label",
            "reschedule_count",
            "reschedule_history",
            "triggered_by_event",
            "metadata",
            "is_overdue",
            "comment_count",
            "comments",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "completed_at",
            "reschedule_count",
            "reschedule_history",
            "created_by",
            "is_overdue",
            "comment_count",
            "comments",
        ]

    def get_status_label(self, obj) -> str:
        return dict(LeadTaskStatus.CHOICES).get(obj.status, obj.status)

    def get_status_color(self, obj) -> str:
        colors = {
            LeadTaskStatus.TODO: "default",
            LeadTaskStatus.IN_PROGRESS: "processing",
            LeadTaskStatus.DONE: "success",
            LeadTaskStatus.CANCELLED: "error",
        }
        return colors.get(obj.status, "default")

    def get_priority_label(self, obj) -> str:
        return dict(LeadTaskPriority.CHOICES).get(obj.priority, obj.priority)

    def get_priority_color(self, obj) -> str:
        # Note : On s'assure que LeadTaskPriority possède COLOR_MAP
        return getattr(LeadTaskPriority, 'COLOR_MAP', {}).get(obj.priority, "#8c8c8c")

    def get_task_type_label(self, obj) -> str | None:
        return obj.task_type.label if obj.task_type else None

    def get_assigned_to_label(self, obj) -> str | None:
        if not obj.assigned_to:
            return None
        return f"{obj.assigned_to.first_name} {obj.assigned_to.last_name}".strip() or obj.assigned_to.email

    def get_created_by_label(self, obj) -> str | None:
        if not obj.created_by:
            return None
        return f"{obj.created_by.first_name} {obj.created_by.last_name}".strip() or obj.created_by.email

    def get_is_overdue(self, obj) -> bool:
        return obj.is_overdue

    def get_comment_count(self, obj) -> int:
        # Utilise prefetch si disponible, sinon count()
        if hasattr(obj, "_prefetched_objects_cache") and "comments" in obj._prefetched_objects_cache:
            return len(obj._prefetched_objects_cache["comments"])
        return obj.comments.count()