"""
api/leads/lead_search_v2.py

Endpoint de recherche v2 — intelligent.

Améliorations vs v1 :
    ✔ Gestion des espaces : "Jean Dupont" → cherche "Jean" ET "Dupont" séparément
    ✔ Scoring de pertinence : correspondance exacte > début de mot > contenu
    ✔ Résultats triés par score décroissant

URL : GET /api/v2/leads/search/v2/?q=jean+dupont&page=1
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

        base_qs = (
            Lead.objects
            .select_related(
                "status",
                "service",
                "statut_dossier",
                "statut_dossier_interne",
            )
            .prefetch_related(
                "assigned_to",
                "jurist_assigned",
            )
        )

        if not q:
            return base_qs.order_by("-created_at")

        # ── 1. Découper la query en tokens (gestion des espaces) ──────────────
        #
        # "Jean Dupont" → ["jean", "dupont"]
        # "0612"        → ["0612"]
        # "jean  "      → ["jean"]  (strip + filter vides)
        #
        tokens = [t.lower() for t in q.split() if t.strip()]

        # ── 2. Filtre : un lead doit matcher TOUS les tokens ──────────────────
        #
        # Pour chaque token, au moins un champ doit contenir ce token.
        # "Jean Dupont" → first_name|last_name|email|phone contient "jean"
        #              ET first_name|last_name|email|phone contient "dupont"
        #
        combined_filter = Q()
        for token in tokens:
            token_filter = (
                Q(first_name__icontains=token)
                | Q(last_name__icontains=token)
                | Q(email__icontains=token)
                | Q(phone__icontains=token)
            )
            combined_filter &= token_filter

        filtered_qs = base_qs.filter(combined_filter)

        # ── 3. Scoring de pertinence ──────────────────────────────────────────
        #
        # On annote chaque lead avec un score (plus bas = plus pertinent)
        # pour trier les résultats du plus proche au moins proche.
        #
        # Niveaux (par ordre de priorité) :
        #   1 — correspondance exacte sur nom ou prénom  (ex: q="dupont", last_name="Dupont")
        #   2 — début de mot sur nom ou prénom           (ex: q="dup",    last_name="Dupont")
        #   3 — correspondance exacte sur email/phone
        #   4 — contenu partiel sur n'importe quel champ
        #
        # On score sur le premier token — pour "Jean Dupont", "jean" porte le score.
        # Les deux tokens filtrent, mais le score porte sur le terme principal saisi.
        #
        main_token = tokens[0]

        annotated_qs = filtered_qs.annotate(
            relevance=Case(
                # Niveau 1 — exact sur nom/prénom
                When(first_name__iexact=main_token, then=Value(1)),
                When(last_name__iexact=main_token, then=Value(1)),

                # Niveau 2 — commence par le token sur nom/prénom
                When(first_name__istartswith=main_token, then=Value(2)),
                When(last_name__istartswith=main_token, then=Value(2)),

                # Niveau 3 — exact sur email ou téléphone
                When(email__iexact=main_token, then=Value(3)),
                When(phone__iexact=main_token, then=Value(3)),

                # Niveau 4 — contenu partiel (fallback)
                default=Value(4),
                output_field=IntegerField(),
            )
        )

        # Tri : score ASC (meilleur en premier), puis date création DESC
        return annotated_qs.order_by("relevance", "-created_at")