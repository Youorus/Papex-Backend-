from datetime import date, datetime, time
from typing import Optional, Union

from django.db.models import Exists, F, OuterRef, Q
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


def _to_aware(dt_or_d: Optional[Union[datetime, date]], end_of_day: bool = False) -> Optional[datetime]:
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
    """Normalise les valeurs 'avec'/'sans'."""
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

    def get(self, request):
        # --- Query params ---
        raw_date_from = request.query_params.get("date_from")
        raw_date_to = request.query_params.get("date_to")
        raw_appt_from = request.query_params.get("appt_from")
        raw_appt_to = request.query_params.get("appt_to")

        status_code = request.query_params.get("status_code")
        status_id = _to_int_or_none(request.query_params.get("status_id"))
        dossier_code = request.query_params.get("dossier_code")
        dossier_id = _to_int_or_none(request.query_params.get("dossier_id"))

        has_jurist = _normalize_avec_sans(request.query_params.get("has_jurist"))
        has_conseiller = _normalize_avec_sans(request.query_params.get("has_conseiller"))

        # Pagination / tri
        try:
            page = max(int(request.query_params.get("page", 1)), 1)
        except (TypeError, ValueError):
            page = 1

        try:
            page_size = min(max(int(request.query_params.get("page_size", 20)), 1), 200)
        except (TypeError, ValueError):
            page_size = 20

        allowed_ordering = {
            "created_at", "-created_at",
            "appointment_date", "-appointment_date",
            "id", "-id",
        }
        ordering = request.query_params.get("ordering", "-created_at")
        if ordering not in allowed_ordering:
            ordering = "-created_at"

        # --- Parse et convertit les dates ---
        date_from = _to_aware(_parse_iso_any(raw_date_from), end_of_day=False)
        date_to = _to_aware(_parse_iso_any(raw_date_to), end_of_day=True)
        appt_from = _to_aware(_parse_iso_any(raw_appt_from), end_of_day=False)
        appt_to = _to_aware(_parse_iso_any(raw_appt_to), end_of_day=True)

        # --- Base queryset ---
        ThroughConseiller = Lead.assigned_to.through
        ThroughJurist = Lead.jurist_assigned.through

        qs = (
            Lead.objects
            .select_related("status", "statut_dossier")
            .prefetch_related("jurist_assigned", "assigned_to")
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

        # --- Filtres de dates ---
        if date_from:
            qs = qs.filter(created_at__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__lte=date_to)

        # --- Filtres appointment_date ---
        # ⚠️ IMPORTANT : Filter sur appointment_date nécessite Q objects pour gérer NULL
        if appt_from and appt_to:
            # Si les deux dates sont présentes
            qs = qs.filter(
                appointment_date__isnull=False,
                appointment_date__gte=appt_from,
                appointment_date__lte=appt_to
            )
        elif appt_from:
            # Seulement date de début
            qs = qs.filter(
                appointment_date__isnull=False,
                appointment_date__gte=appt_from
            )
        elif appt_to:
            # Seulement date de fin
            qs = qs.filter(
                appointment_date__isnull=False,
                appointment_date__lte=appt_to
            )

        # --- Filtres statut ---
        # Priorité à l'ID si les deux sont fournis
        if status_id is not None:
            qs = qs.filter(status_id=status_id)
        elif status_code:
            qs = qs.filter(status__code=status_code)

        # --- Filtres statut dossier ---
        if dossier_id is not None:
            qs = qs.filter(statut_dossier_id=dossier_id)
        elif dossier_code:
            qs = qs.filter(statut_dossier__code=dossier_code)

        # --- Filtres assignations ---
        if has_jurist == "avec":
            qs = qs.filter(has_jurist=True)
        elif has_jurist == "sans":
            qs = qs.filter(has_jurist=False)

        if has_conseiller == "avec":
            qs = qs.filter(has_conseiller=True)
        elif has_conseiller == "sans":
            qs = qs.filter(has_conseiller=False)

        # --- Total (AVANT pagination) ---
        total = qs.count()

        # --- KPI FILTRÉS (calculés sur le queryset filtré) ---
        today = now().date()

        # RDV aujourd'hui (UNIQUEMENT RDV_PLANIFIE et RDV_CONFIRME)
        rdv_today = qs.filter(
            appointment_date__date=today,
            status__code__in=[RDV_PLANIFIE, RDV_CONFIRME]
        ).count()

        # Contrats aujourd'hui liés aux leads filtrés
        # ⚠️ Optimisation : utiliser values_list avec flat=True
        filtered_lead_ids = qs.values_list('id', flat=True)
        contracts_today = Contract.objects.filter(
            client__lead_id__in=filtered_lead_ids,
            created_at__date=today
        ).count()

        # --- Pagination & tri ---
        qs = qs.order_by(ordering)
        start = (page - 1) * page_size
        end = start + page_size

        leads = qs[start:end]

        # --- Serialization ---
        rows = []
        for lead in leads:
            rows.append({
                "id": lead.id,
                "first_name": lead.first_name,
                "last_name": lead.last_name,
                "email": lead.email,
                "phone": lead.phone,
                "created_at": lead.created_at.isoformat() if lead.created_at else None,
                "appointment_date": lead.appointment_date.isoformat() if lead.appointment_date else None,
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
                    {"id": u.id, "first_name": u.first_name, "last_name": u.last_name}
                    for u in lead.jurist_assigned.all()
                ],
                "conseillers": [
                    {"id": u.id, "first_name": u.first_name, "last_name": u.last_name}
                    for u in lead.assigned_to.all()
                ],
            })

        # --- Calcul du nombre de pages ---
        total_pages = (total + page_size - 1) // page_size if total > 0 else 1

        return Response(
            {
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "ordering": ordering,
                "items": rows,
                "kpi": {
                    "rdv_today": rdv_today,
                    "contracts_today": contracts_today,
                },
            }
        )