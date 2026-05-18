from django.db.models import Count
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from api.creators.filters import CreatorProfileFilter, SocialAccountLeadFilter
from api.creators.models import CreatorProfile, SocialAccountLead
from api.creators.pagination import StandardResultsSetPagination
from api.creators.permissions import IsAdminOrStaff
from api.creators.serializers import (
    CreatorProfileCreateSerializer,
    CreatorProfileSerializer,
    CreatorProfileUpdateSerializer,
    SocialAccountLeadCreateUpdateSerializer,
    SocialAccountLeadSerializer,
)


class CreatorProfileViewSet(viewsets.ModelViewSet):
    queryset = CreatorProfile.objects.select_related("user").all()
    permission_classes = [IsAdminOrStaff]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = CreatorProfileFilter
    pagination_class = StandardResultsSetPagination

    search_fields = [
        "user__email",
        "user__first_name",
        "user__last_name",
        "promo_code",
        "phone_number",
        "country",
        "city",
    ]

    ordering_fields = [
        "created_at",
        "updated_at",
        "commission_rate",
        "promo_code",
        "user__email",
    ]

    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.action == "create":
            return CreatorProfileCreateSerializer

        if self.action in ["update", "partial_update"]:
            return CreatorProfileUpdateSerializer

        return CreatorProfileSerializer

    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        queryset = self.filter_queryset(self.get_queryset())

        return Response(
            {
                "total": queryset.count(),
                "active": queryset.filter(status=CreatorProfile.Status.ACTIVE).count(),
                "pending": queryset.filter(status=CreatorProfile.Status.PENDING).count(),
                "paused": queryset.filter(status=CreatorProfile.Status.PAUSED).count(),
                "disabled": queryset.filter(
                    status=CreatorProfile.Status.DISABLED
                ).count(),
            }
        )


class SocialAccountLeadViewSet(viewsets.ModelViewSet):
    queryset = SocialAccountLead.objects.select_related("creator__user").all()
    permission_classes = [IsAdminOrStaff]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = SocialAccountLeadFilter
    pagination_class = StandardResultsSetPagination

    search_fields = [
        "username",
        "display_name",
        "profile_url",
        "bio",
        "country",
        "language",
        "categories",
        "source",
        "notes",
    ]

    ordering_fields = [
        "created_at",
        "updated_at",
        "followers_count",
        "username",
        "display_name",
        "country",
        "language",
        "source",
    ]

    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return SocialAccountLeadCreateUpdateSerializer

        return SocialAccountLeadSerializer

    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        queryset = self.filter_queryset(self.get_queryset())

        status_counts = queryset.values("contact_status").annotate(count=Count("id"))
        status_map = {item["contact_status"]: item["count"] for item in status_counts}

        return Response(
            {
                "total": queryset.count(),
                "viable": queryset.filter(is_viable=True).count(),
                "not_viable": queryset.filter(is_viable=False).count(),
                "new": status_map.get(SocialAccountLead.ContactStatus.NEW, 0),
                "to_contact": status_map.get(
                    SocialAccountLead.ContactStatus.TO_CONTACT, 0
                ),
                "contacted": status_map.get(
                    SocialAccountLead.ContactStatus.CONTACTED, 0
                ),
                "positive": status_map.get(
                    SocialAccountLead.ContactStatus.POSITIVE, 0
                ),
                "negative": status_map.get(
                    SocialAccountLead.ContactStatus.NEGATIVE, 0
                ),
                "converted": status_map.get(
                    SocialAccountLead.ContactStatus.CONVERTED, 0
                ),
                "not_relevant": status_map.get(
                    SocialAccountLead.ContactStatus.NOT_RELEVANT, 0
                ),
                "with_creator": queryset.filter(creator__isnull=False).count(),
                "without_creator": queryset.filter(creator__isnull=True).count(),
            }
        )

    @action(detail=True, methods=["post"], url_path="mark_contacted")
    def mark_contacted(self, request, pk=None):
        lead = self.get_object()
        lead.contact_status = SocialAccountLead.ContactStatus.CONTACTED
        lead.save(update_fields=["contact_status", "updated_at"])

        serializer = self.get_serializer(lead)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="mark_positive")
    def mark_positive(self, request, pk=None):
        lead = self.get_object()
        lead.contact_status = SocialAccountLead.ContactStatus.POSITIVE
        lead.save(update_fields=["contact_status", "updated_at"])

        serializer = self.get_serializer(lead)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="mark_negative")
    def mark_negative(self, request, pk=None):
        lead = self.get_object()
        lead.contact_status = SocialAccountLead.ContactStatus.NEGATIVE
        lead.save(update_fields=["contact_status", "updated_at"])

        serializer = self.get_serializer(lead)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="mark_not_relevant")
    def mark_not_relevant(self, request, pk=None):
        lead = self.get_object()
        lead.contact_status = SocialAccountLead.ContactStatus.NOT_RELEVANT
        lead.save(update_fields=["contact_status", "updated_at"])

        serializer = self.get_serializer(lead)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="link_creator")
    def link_creator(self, request, pk=None):
        lead = self.get_object()
        creator_id = request.data.get("creator_id")

        if not creator_id:
            return Response(
                {"creator_id": ["Ce champ est obligatoire."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            creator = CreatorProfile.objects.get(id=creator_id)
        except CreatorProfile.DoesNotExist:
            return Response(
                {"creator_id": ["Créateur introuvable."]},
                status=status.HTTP_404_NOT_FOUND,
            )

        lead.creator = creator
        lead.contact_status = SocialAccountLead.ContactStatus.CONVERTED
        lead.save(update_fields=["creator", "contact_status", "updated_at"])

        serializer = self.get_serializer(lead)
        return Response(serializer.data, status=status.HTTP_200_OK)