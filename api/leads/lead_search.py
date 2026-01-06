from datetime import date, datetime, time
from typing import Optional, Union

from django.db.models import Exists, F, OuterRef, Prefetch
from django.utils.dateparse import parse_date, parse_datetime
from django.utils.timezone import get_current_timezone, is_naive, make_aware, now
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.leads.models import Lead
from api.contracts.models import Contract
from api.leads.constants import RDV_CONFIRME, RDV_PLANIFIE


def _parse_iso_any(dt: Optional[str]) -> Optional[Union[datetime, date]]:
    """Parse une date ou datetime ISO."""
    if not dt:
        return None

    # Essayer datetime d'abord
    parsed_dt = parse_datetime(dt)
    if parsed_dt:
        return parsed_dt

    # Sinon essayer date simple
    parsed_date = parse_date(dt)
    if parsed_date:
        return parsed_date

    return None


def _to_aware(
        dt_or_d: Optional[Union[datetime, date]],
        end_of_day: bool = False
) -> Optional[datetime]:
    """Convertit une date/datetime en datetime aware."""
    if dt_or_d is None:
        return None

    tz = get_current_timezone()

    # Si c'est une date simple (pas datetime)
    if isinstance(dt_or_d, date) and not isinstance(dt_or_d, datetime):
        if end_of_day:
            # Fin de journée : 23:59:59.999999
            dt = datetime.combine(dt_or_d, time(23, 59, 59, 999999))
        else:
            # Début de journée : 00:00:00
            dt = datetime.combine(dt_or_d, time(0, 0, 0))
        return make_aware(dt, timezone=tz)

    # Si c'est déjà un datetime
    if isinstance(dt_or_d, datetime):
        if is_naive(dt_or_d):
            return make_aware(dt_or_d, timezone=tz)
        return dt_or_d

    return None


def _normalize_avec_sans(value: Optional[str]) -> Optional[str]:
    """Normalise les valeurs 'avec'/'sans' en booléen."""
    if not value:
        return None

    v = value.strip().lower()
    if v in {"avec", "oui", "with", "true", "1"}:
        return "avec"
    if v in {"sans", "non", "without", "false", "0"}:
        return "sans"

    return None


def _to_int_or_none(val: Optional[str]) -> Optional[int]:
    """Convertit en int ou retourne None."""
    if val is None or val == "":
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


class LeadSearchView(APIView):
    """
    Vue API permettant la recherche et la filtration des leads.

    Query params:
    - date_from: Date/datetime de création minimum (ISO format)
    - date_to: Date/datetime de création maximum (ISO format)
    - appt_from: Date/datetime de RDV minimum (ISO format)
    - appt_to: Date/datetime de RDV maximum (ISO format)
    - status_code: Code du statut lead (ex: 'RDV_PLANIFIE')
    - status_id: ID du statut lead
    - dossier_code: Code du statut dossier
    - dossier_id: ID du statut dossier
    - has_jurist: 'avec' ou 'sans'
    - has_conseiller: 'avec' ou 'sans'
    - page: Numéro de page (défaut: 1)
    - page_size: Taille de page (défaut: 20, max: 200)
    - ordering: Tri (-created_at, created_at, -appointment_date, etc.)
    """

    permission_classes = [IsAuthenticated]

    # Constantes de configuration
    DEFAULT_PAGE = 1
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 200
    DEFAULT_ORDERING = "-created_at"

    ALLOWED_ORDERING = {
        "created_at",
        "-created_at",
        "appointment_date",
        "-appointment_date",
        "id",
        "-id",
        "first_name",
        "-first_name",
        "last_name",
        "-last_name",
    }

    def get(self, request):
        # --- Extraction et validation des paramètres ---
        filters = self._extract_filters(request.query_params)
        pagination = self._extract_pagination(request.query_params)

        # --- Construction du queryset de base ---
        qs = self._build_base_queryset()

        # --- Application des filtres ---
        qs = self._apply_filters(qs, filters)

        # --- Calcul du total AVANT pagination ---
        total = qs.count()

        # --- Calcul des KPI sur le queryset filtré ---
        kpi = self._calculate_kpi(qs)

        # --- Application du tri et de la pagination ---
        qs = qs.order_by(pagination["ordering"])
        start = (pagination["page"] - 1) * pagination["page_size"]
        end = start + pagination["page_size"]
        leads = qs[start:end]

        # --- Sérialisation ---
        rows = self._serialize_leads(leads)

        # --- Calcul du nombre de pages ---
        total_pages = (
            (total + pagination["page_size"] - 1) // pagination["page_size"]
            if total > 0
            else 1
        )

        return Response({
            "total": total,
            "page": pagination["page"],
            "page_size": pagination["page_size"],
            "total_pages": total_pages,
            "ordering": pagination["ordering"],
            "items": rows,
            "kpi": kpi,
        })

    def _extract_filters(self, query_params):
        """Extrait et valide tous les paramètres de filtre."""
        # Dates de création
        date_from = _to_aware(
            _parse_iso_any(query_params.get("date_from")),
            end_of_day=False
        )
        date_to = _to_aware(
            _parse_iso_any(query_params.get("date_to")),
            end_of_day=True
        )

        # Dates de RDV
        appt_from = _to_aware(
            _parse_iso_any(query_params.get("appt_from")),
            end_of_day=False
        )
        appt_to = _to_aware(
            _parse_iso_any(query_params.get("appt_to")),
            end_of_day=True
        )

        # Statuts
        status_code = query_params.get("status_code")
        status_id = _to_int_or_none(query_params.get("status_id"))
        dossier_code = query_params.get("dossier_code")
        dossier_id = _to_int_or_none(query_params.get("dossier_id"))

        # Assignations
        has_jurist = _normalize_avec_sans(query_params.get("has_jurist"))
        has_conseiller = _normalize_avec_sans(query_params.get("has_conseiller"))

        return {
            "date_from": date_from,
            "date_to": date_to,
            "appt_from": appt_from,
            "appt_to": appt_to,
            "status_code": status_code,
            "status_id": status_id,
            "dossier_code": dossier_code,
            "dossier_id": dossier_id,
            "has_jurist": has_jurist,
            "has_conseiller": has_conseiller,
        }

    def _extract_pagination(self, query_params):
        """Extrait et valide les paramètres de pagination."""
        try:
            page = max(int(query_params.get("page", self.DEFAULT_PAGE)), 1)
        except (TypeError, ValueError):
            page = self.DEFAULT_PAGE

        try:
            page_size = min(
                max(int(query_params.get("page_size", self.DEFAULT_PAGE_SIZE)), 1),
                self.MAX_PAGE_SIZE
            )
        except (TypeError, ValueError):
            page_size = self.DEFAULT_PAGE_SIZE

        ordering = query_params.get("ordering", self.DEFAULT_ORDERING)
        if ordering not in self.ALLOWED_ORDERING:
            ordering = self.DEFAULT_ORDERING

        return {
            "page": page,
            "page_size": page_size,
            "ordering": ordering,
        }

    def _build_base_queryset(self):
        """Construit le queryset de base avec toutes les annotations."""
        ThroughConseiller = Lead.assigned_to.through
        ThroughJurist = Lead.jurist_assigned.through

        return (
            Lead.objects
            .select_related("status", "statut_dossier")
            .prefetch_related(
                Prefetch(
                    "jurist_assigned",
                    queryset=Lead.jurist_assigned.related.related_model.objects.only(
                        "id", "first_name", "last_name"
                    )
                ),
                Prefetch(
                    "assigned_to",
                    queryset=Lead.assigned_to.related.related_model.objects.only(
                        "id", "first_name", "last_name"
                    )
                ),
            )
            .annotate(
                has_conseiller=Exists(
                    ThroughConseiller.objects.filter(lead_id=OuterRef("pk"))
                ),
                has_jurist=Exists(
                    ThroughJurist.objects.filter(lead_id=OuterRef("pk"))
                ),
                lead_status_code=F("status__code"),
                lead_status_label=F("status__label"),
                lead_status_color=F("status__color"),
                statut_dossier_code=F("statut_dossier__code"),
                statut_dossier_label=F("statut_dossier__label"),
                statut_dossier_color=F("statut_dossier__color"),
            )
        )

    def _apply_filters(self, qs, filters):
        """Applique tous les filtres au queryset."""
        # Filtres de dates de création
        if filters["date_from"]:
            qs = qs.filter(created_at__gte=filters["date_from"])
        if filters["date_to"]:
            qs = qs.filter(created_at__lte=filters["date_to"])

        # Filtres de dates de RDV
        if filters["appt_from"] or filters["appt_to"]:
            # Toujours exclure les NULL quand on filtre sur appointment_date
            qs = qs.filter(appointment_date__isnull=False)

            if filters["appt_from"]:
                qs = qs.filter(appointment_date__gte=filters["appt_from"])
            if filters["appt_to"]:
                qs = qs.filter(appointment_date__lte=filters["appt_to"])

        # Filtres de statut (priorité à l'ID)
        if filters["status_id"] is not None:
            qs = qs.filter(status_id=filters["status_id"])
        elif filters["status_code"]:
            qs = qs.filter(status__code=filters["status_code"])

        # Filtres de statut dossier (priorité à l'ID)
        if filters["dossier_id"] is not None:
            qs = qs.filter(statut_dossier_id=filters["dossier_id"])
        elif filters["dossier_code"]:
            qs = qs.filter(statut_dossier__code=filters["dossier_code"])

        # Filtres d'assignation
        if filters["has_jurist"] == "avec":
            qs = qs.filter(has_jurist=True)
        elif filters["has_jurist"] == "sans":
            qs = qs.filter(has_jurist=False)

        if filters["has_conseiller"] == "avec":
            qs = qs.filter(has_conseiller=True)
        elif filters["has_conseiller"] == "sans":
            qs = qs.filter(has_conseiller=False)

        return qs

    def _calculate_kpi(self, filtered_qs):
        """Calcule les KPI sur le queryset filtré."""
        today = now().date()

        # RDV aujourd'hui (UNIQUEMENT RDV_PLANIFIE et RDV_CONFIRME)
        rdv_today = filtered_qs.filter(
            appointment_date__date=today,
            status__code__in=[RDV_PLANIFIE, RDV_CONFIRME]
        ).count()

        # Contrats aujourd'hui liés aux leads filtrés
        # Optimisation : utiliser values_list avec flat=True
        filtered_lead_ids = list(filtered_qs.values_list('id', flat=True))

        contracts_today = 0
        if filtered_lead_ids:  # Éviter une requête vide
            contracts_today = Contract.objects.filter(
                client__lead_id__in=filtered_lead_ids,
                created_at__date=today
            ).count()

        return {
            "rdv_today": rdv_today,
            "contracts_today": contracts_today,
        }

    def _serialize_leads(self, leads):
        """Sérialise les leads en dictionnaires."""
        rows = []
        for lead in leads:
            rows.append({
                "id": lead.id,
                "first_name": lead.first_name,
                "last_name": lead.last_name,
                "email": lead.email,
                "phone": lead.phone,
                "created_at": lead.created_at.isoformat() if lead.created_at else None,
                "appointment_date": (
                    lead.appointment_date.isoformat()
                    if lead.appointment_date
                    else None
                ),
                "status_id": lead.status_id,
                "statut_dossier_id": lead.statut_dossier_id,
                "lead_status_code": lead.lead_status_code,
                "lead_status_label": lead.lead_status_label,
                "lead_status_color": lead.lead_status_color,
                "statut_dossier_code": lead.statut_dossier_code,
                "statut_dossier_label": lead.statut_dossier_label,
                "statut_dossier_color": lead.statut_dossier_color,
                "has_conseiller": lead.has_conseiller,
                "has_jurist": lead.has_jurist,
                "jurists": [
                    {
                        "id": u.id,
                        "first_name": u.first_name,
                        "last_name": u.last_name
                    }
                    for u in lead.jurist_assigned.all()
                ],
                "conseillers": [
                    {
                        "id": u.id,
                        "first_name": u.first_name,
                        "last_name": u.last_name
                    }
                    for u in lead.assigned_to.all()
                ],
            })
        return rows