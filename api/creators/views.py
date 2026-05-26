from datetime import datetime
from decimal import Decimal

from django.db.models import Count, Sum, F, ExpressionWrapper, DecimalField, Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from api.contracts.models import Contract
from api.creators.filters import CreatorProfileFilter, SocialAccountLeadFilter, CreatorKpiFilter
from api.creators.models import CreatorProfile, SocialAccountLead, PromoCode, CreatorContract
from api.creators.pagination import StandardResultsSetPagination
from api.creators.permissions import IsAdminOrStaff, IsAdminOrCreator
from api.creators.serializers import (
    CreatorProfileCreateSerializer,
    CreatorProfileSerializer,
    CreatorProfileUpdateSerializer,
    SocialAccountLeadCreateUpdateSerializer,
    SocialAccountLeadSerializer, CreatorKpiSerializer, PromoCodeSerializer, CreatorAggregateKpiSerializer,
    CreatorContractSerializer,
)
from api.leads.models import Lead
from api.users.roles import UserRoles



class CreatorProfileViewSet(viewsets.ModelViewSet):
    queryset = CreatorProfile.objects.select_related("user").all()
    permission_classes = [IsAdminOrCreator]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = CreatorProfileFilter
    pagination_class = StandardResultsSetPagination

    search_fields = [
        "user__email",
        "user__first_name",
        "user__last_name",
        "phone_number",
        "country",
        "city",
    ]

    ordering_fields = [
        "created_at",
        "updated_at",
        "user__email",
    ]

    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or getattr(user, "role", None) == UserRoles.ACCUEIL:
            return super().get_queryset()
        return super().get_queryset().filter(user=user)

    def get_serializer_class(self):
        if self.action == "create":
            return CreatorProfileCreateSerializer

        if self.action in ["update", "partial_update"]:
            return CreatorProfileUpdateSerializer

        return CreatorProfileSerializer

    @action(detail=False, methods=["get"])
    def me(self, request):
        """
        Récupère le profil du créateur connecté.
        """
        try:
            creator = request.user.creator_profile
            serializer = self.get_serializer(creator)
            return Response(serializer.data)
        except CreatorProfile.DoesNotExist:
            return Response({"detail": "Aucun profil créateur trouvé."}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=["get"], url_path="stats", permission_classes=[IsAdminOrStaff])
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

    @action(detail=True, methods=["get"], url_path="kpis")
    def kpis(self, request, pk=None):
        creator = self.get_object()

        start_date_str = request.query_params.get("start_date")
        end_date_str = request.query_params.get("end_date")

        leads_queryset = creator.leads.all()
        contracts_queryset = Contract.objects.filter(client__lead__creator_profile=creator, is_cancelled=False)

        try:
            if start_date_str:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                leads_queryset = leads_queryset.filter(created_at__date__gte=start_date)
                contracts_queryset = contracts_queryset.filter(created_at__date__gte=start_date)

            if end_date_str:
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                leads_queryset = leads_queryset.filter(created_at__date__lte=end_date)
                contracts_queryset = contracts_queryset.filter(created_at__date__lte=end_date)

        except ValueError:
            return Response(
                {"error": "Invalid date format. Please use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST
            )

        total_leads = leads_queryset.count()
        total_contracts = contracts_queryset.count()

        aggregation = contracts_queryset.aggregate(total=Sum('amount_due'))
        total_revenue = aggregation['total'] or Decimal("0.00")
        
        total_commissions = Decimal("0.00")

        if total_contracts > 0:
            for contract in contracts_queryset.select_related('client__lead__promo_code'):
                # Using the real_amount property from the Contract model
                real_amount = contract.real_amount
                promo_code = contract.client.lead.promo_code
                if promo_code:
                    commission_rate = promo_code.commission_rate or Decimal("0.00")
                    bonus_amount = promo_code.bonus_amount or Decimal("0.00")
                    total_commissions += (real_amount * commission_rate / Decimal("100.00")) + bonus_amount

        conversion_rate = (total_contracts / total_leads * 100) if total_leads > 0 else 0.0

        data = {
            "total_leads": total_leads,
            "total_contracts": total_contracts,
            "conversion_rate": round(float(conversion_rate), 2),
            "total_revenue": total_revenue,
            "total_commissions": total_commissions.quantize(Decimal('0.01')),
            "currency": creator.currency or "EUR",
        }

        # Use data as the instance for the serializer to ensure read_only fields are populated
        serializer = CreatorKpiSerializer(data)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="aggregate-kpis", permission_classes=[IsAdminOrStaff])
    def aggregate_kpis(self, request):
        self.filterset_class = CreatorKpiFilter
        queryset = self.get_queryset()
        
        # Instantiate filterset manually to get cleaned_data
        filterset = self.filterset_class(request.GET, queryset=queryset)
        if not filterset.is_valid():
            return Response(filterset.errors, status=status.HTTP_400_BAD_REQUEST)
        
        filtered_queryset = filterset.qs

        start_date = filterset.form.cleaned_data.get("leads_date_range_after")
        end_date = filterset.form.cleaned_data.get("leads_date_range_before")

        contracts_filter = Q(client__lead__promo_code__isnull=False, is_cancelled=False)
        if start_date:
            contracts_filter &= Q(created_at__date__gte=start_date)
        if end_date:
            contracts_filter &= Q(created_at__date__lte=end_date)

        contracts = Contract.objects.filter(contracts_filter).select_related('client__lead__promo_code__creator__user')
        
        creator_kpis = {}

        for contract in contracts:
            creator = contract.client.lead.promo_code.creator
            # Check if this creator is in our filtered queryset of creators
            if not filtered_queryset.filter(id=creator.id).exists():
                continue

            if creator.id not in creator_kpis:
                creator_kpis[creator.id] = {
                    "creator_id": creator.id,
                    "creator_full_name": creator.user.get_full_name(),
                    "creator_currency": creator.currency,
                    "total_leads": 0,
                    "total_contracts": 0,
                    "total_revenue": Decimal("0.00"),
                    "total_commissions": Decimal("0.00"),
                }
            
            promo_code = contract.client.lead.promo_code
            real_amount = contract.real_amount
            commission = (real_amount * promo_code.commission_rate / Decimal("100.00")) + promo_code.bonus_amount

            creator_kpis[creator.id]["total_contracts"] += 1
            creator_kpis[creator.id]["total_revenue"] += contract.amount_due
            creator_kpis[creator.id]["total_commissions"] += commission

        leads_filter = Q(creator_profile__in=filtered_queryset)
        if start_date:
            leads_filter &= Q(created_at__date__gte=start_date)
        if end_date:
            leads_filter &= Q(created_at__date__lte=end_date)
            
        leads = Lead.objects.filter(leads_filter)
        leads_per_creator = leads.values('creator_profile').annotate(total=Count('id'))

        for lead_data in leads_per_creator:
            creator_id = lead_data['creator_profile']
            if creator_id in creator_kpis:
                creator_kpis[creator_id]['total_leads'] = lead_data['total']
            else:
                # If the creator had leads but no contracts, we still want to show them if they match filters
                try:
                    creator = filtered_queryset.get(id=creator_id)
                    creator_kpis[creator_id] = {
                        "creator_id": creator.id,
                        "creator_full_name": creator.user.get_full_name(),
                        "creator_currency": creator.currency,
                        "total_leads": lead_data['total'],
                        "total_contracts": 0,
                        "total_revenue": Decimal("0.00"),
                        "total_commissions": Decimal("0.00"),
                    }
                except CreatorProfile.DoesNotExist:
                    continue

        # Ensure creators with NO leads and NO contracts but matching filters are also included if they exist in filtered_queryset
        for creator in filtered_queryset:
            if creator.id not in creator_kpis:
                creator_kpis[creator.id] = {
                    "creator_id": creator.id,
                    "creator_full_name": creator.user.get_full_name(),
                    "creator_currency": creator.currency or "EUR",
                    "total_leads": 0,
                    "total_contracts": 0,
                    "total_revenue": Decimal("0.00"),
                    "total_commissions": Decimal("0.00"),
                }

        final_creator_kpis = []
        for kpi in creator_kpis.values():
            if kpi['total_leads'] > 0:
                kpi['conversion_rate'] = round((kpi['total_contracts'] / kpi['total_leads']) * 100, 2)
            else:
                kpi['conversion_rate'] = 0.0
            
            # Formattage des décimaux
            kpi['total_revenue'] = kpi['total_revenue'].quantize(Decimal('0.01'))
            kpi['total_commissions'] = kpi['total_commissions'].quantize(Decimal('0.01'))
            final_creator_kpis.append(kpi)

        summary = {
            "total_leads": sum(kpi['total_leads'] for kpi in final_creator_kpis),
            "total_contracts": sum(kpi['total_contracts'] for kpi in final_creator_kpis),
            "total_revenue": sum(kpi['total_revenue'] for kpi in final_creator_kpis),
            "total_commissions": sum(kpi['total_commissions'] for kpi in final_creator_kpis),
        }

        if summary['total_leads'] > 0:
            summary['average_conversion_rate'] = round((summary['total_contracts'] / summary['total_leads']) * 100, 2)
        else:
            summary['average_conversion_rate'] = 0.0

        response_data = {
            "summary": summary,
            "creators": CreatorAggregateKpiSerializer(final_creator_kpis, many=True).data,
        }

        return Response(response_data)


class PromoCodeViewSet(viewsets.ModelViewSet):
    queryset = PromoCode.objects.select_related("creator__user").all()
    serializer_class = PromoCodeSerializer
    permission_classes = [IsAdminOrCreator]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["code", "creator__user__email", "creator__user__first_name"]
    ordering_fields = ["created_at", "valid_until", "commission_rate", "bonus_amount"]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset()

        if user.is_superuser or getattr(user, "role", None) == UserRoles.ACCUEIL:
            if self.action == "list":
                return queryset.select_related("creator", "creator__user")
            return queryset

        return queryset.filter(creator__user=user)


class CreatorContractViewSet(viewsets.ModelViewSet):
    queryset = CreatorContract.objects.select_related("creator__user").all()
    serializer_class = CreatorContractSerializer
    permission_classes = [IsAdminOrCreator]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["title", "creator__user__email", "creator__user__first_name"]
    ordering_fields = ["created_at", "title"]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset()

        if user.is_superuser or getattr(user, "role", None) == UserRoles.ACCUEIL:
            return queryset

        return queryset.filter(creator__user=user)

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAdminOrStaff()]
        return [IsAdminOrCreator()]


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