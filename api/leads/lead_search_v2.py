"""
api/leads/lead_search_v2.py
Recherche Globale : Permet de trouver tout lead par son nom, email ou téléphone.
"""

from rest_framework import generics, filters, permissions
from django.db.models import Q, Case, When, Value, IntegerField
from api.core.pagination import CRMLeadPagination
from api.leads.models import Lead
from api.leads.serializers import LeadSerializer


class LeadSearchViewV2(generics.ListAPIView):

    serializer_class = LeadSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = CRMLeadPagination
    filter_backends = [filters.OrderingFilter]

    def get_queryset(self):
        q = self.request.query_params.get("q", "").strip()

        # ── 0. Base Globale (On ne filtre pas par jurist_assigned ici) ────────
        base_qs = (
            Lead.objects
            .select_related("status", "statut_dossier", "statut_dossier_interne")
            .prefetch_related("assigned_to", "jurist_assigned")
        )

        if not q:
            return base_qs.order_by("-created_at")

        # ── 1. Tokens ──────────────
        tokens = [t.lower() for t in q.split() if t.strip()]

        # ── 2. Filtre de recherche ──────────────
        combined_filter = Q()
        for token in tokens:
            token_filter = (
                Q(first_name__icontains=token)
                | Q(last_name__icontains=token)
                | Q(email__icontains=token)
                | Q(phone__icontains=token)
            )
            combined_filter &= token_filter

        # ── 3. Scoring de pertinence ──────────────
        main_token = tokens[0]
        return base_qs.filter(combined_filter).annotate(
            relevance=Case(
                When(first_name__iexact=main_token, then=Value(1)),
                When(last_name__iexact=main_token, then=Value(1)),
                When(email__iexact=main_token, then=Value(3)),
                When(phone__iexact=main_token, then=Value(3)),
                default=Value(4),
                output_field=IntegerField(),
            )
        ).order_by("relevance", "-created_at")