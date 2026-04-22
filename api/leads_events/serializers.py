"""
api/leads/events/serializers.py

Sérialiseurs pour le système de tree d'événements.
"""

from rest_framework import serializers
from .models import LeadEvent
from api.documents.serializers import DocumentSerializer


class LeadEventSerializer(serializers.ModelSerializer):
    """
    Serializer plat — utilisé pour la création et les opérations unitaires.
    """

    actor_name = serializers.SerializerMethodField()
    event_label = serializers.CharField(source="event_type.label", read_only=True)
    event_code = serializers.CharField(source="event_type.code", read_only=True)
    event_color = serializers.SerializerMethodField()

    # Write-only : IDs des documents à attacher
    attachment_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
    )

    # Read-only : documents détaillés
    attachments = DocumentSerializer(many=True, read_only=True)

    class Meta:
        model = LeadEvent
        fields = [
            "id",
            "lead",
            "event_type",
            "event_code",
            "event_label",
            "event_color",
            "actor",
            "actor_name",
            "parent_event",
            "data",
            "note",
            "occurred_at",
            "position_x",
            "position_y",
            "attachments",
            "attachment_ids",
        ]
        read_only_fields = ["id", "occurred_at", "attachments"]

    def get_actor_name(self, obj):
        if obj.actor:
            return obj.actor.get_full_name()
        return "Système"

    def get_event_color(self, obj):
        """
        Retourne la couleur associée au type d'événement (depuis data ou défaut).
        """
        return getattr(obj.event_type, "color", "#6366f1") or "#6366f1"

    def create(self, validated_data):
        attachment_ids = validated_data.pop("attachment_ids", [])
        event = super().create(validated_data)
        if attachment_ids:
            from api.documents.models import Document
            docs = Document.objects.filter(pk__in=attachment_ids)
            event.attachments.set(docs)
        return event


class LeadEventNodeSerializer(serializers.ModelSerializer):
    """
    Serializer optimisé pour le rendu React Flow.
    Renvoie le format attendu par React Flow : { id, type, position, data }.
    """

    actor_name = serializers.SerializerMethodField()
    event_label = serializers.CharField(source="event_type.label", read_only=True)
    event_code = serializers.CharField(source="event_type.code", read_only=True)
    children_ids = serializers.SerializerMethodField()
    attachments_count = serializers.SerializerMethodField()

    class Meta:
        model = LeadEvent
        fields = [
            "id",
            "lead",
            "event_type",
            "event_code",
            "event_label",
            "actor",
            "actor_name",
            "parent_event",
            "children_ids",
            "data",
            "note",
            "occurred_at",
            "position_x",
            "position_y",
            "attachments_count",
        ]

    def get_actor_name(self, obj):
        if obj.actor:
            return obj.actor.get_full_name()
        return "Système"

    def get_children_ids(self, obj):
        return list(obj.children.values_list("id", flat=True))

    def get_attachments_count(self, obj):
        return obj.attachments.count()


class LeadTimelineSerializer(serializers.Serializer):
    """
    Sérialiseur pour le format React Flow complet :
    { nodes: [...], edges: [...] }
    """

    nodes = serializers.ListField()
    edges = serializers.ListField()