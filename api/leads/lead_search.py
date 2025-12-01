from datetime import date, datetime, time
from typing import Optional

from django.db.models import Exists, F, OuterRef, Q
from django.utils.dateparse import parse_date, parse_datetime
from django.utils.timezone import get_current_timezone, is_naive, make_aware, now
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.leads.models import Lead
from api.contracts.models import Contract
from api.leads.constants import RDV_CONFIRME, RDV_PLANIFIE


def _parse_iso_any(dt: Optional[str]) -> Optional[object]:
    if not dt:
        return None
    return parse_datetime(dt) or parse_date(dt)


def _to_aware(dt_or_d: Optional[object], end_of_day: bool = False) -> Optional[datetime]:
    if dt_or_d is None:
        return None

    tz = get_current_timezone()

    if isinstance(dt_or_d, date) and not isinstance(dt_or_d, datetime):
        if end_of_day:
            dt = datetime.combine(dt_or_d, time(23, 59, 59, 999999))
        else:
            dt = datetime.combine(dt_or_d, time(0, 0, 0, 0))
        return make_aware(dt, timezone=tz)

    dt = dt_or_d
    if is_naive(dt):
        return make_aware(dt, timezone=tz)
    return dt


def _normalize_avec_sans(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    v = value.strip().lower()
    if v in {"avec", "oui", "with", "true", "1"}:
        return "avec"
    if v in {"sans", "non", "without", "false", "0"}:
        return "sans"
    return None


def _to_int_or_none(val: Optional[str]) -> Optional[int]:
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


class LeadSearchView(APIView):
    """
    Vue API permettant la recherche et la filtration des leads,
    avec ajout des KPI filtrés (rdv_today uniquement RDV_PLANIFIE et RDV_CONFIRME)
    et retour des juristes / conseillers assignés.
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
        has_conseille = _normalize_avec_sans(request.query_params.get("has_conseiller"))

        # Pagination / tri
        try:
            page = max(int(request.query_params.get("page", 1)), 1)
        except Exception:
            page = 1
        try:
            page_size = min(max(int(request.query_params.get("page_size", 20)), 1), 200)
        except Exception:
            page_size = 20

        allowed_ordering = {
            "created_at", "-created_at",
            "appointment_date", "-appointment_date",
            "id", "-id",
        }
        ordering = request.query_params.get("ordering", "-created_at")
        if ordering not in allowed_ordering:
            ordering = "-created_at"

        # --- Dates ---
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

        # --- Filtres ---
        if date_from:
            qs = qs.filter(created_at__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__lte=date_to)

        if appt_from:
            qs = qs.filter(appointment_date__isnull=False, appointment_date__gte=appt_from)
        if appt_to:
            qs = qs.filter(appointment_date__isnull=False, appointment_date__lte=appt_to)

        if status_id is not None:
            qs = qs.filter(status_id=status_id)
        elif status_code:
            qs = qs.filter(status__code=status_code)

        if dossier_id is not None:
            qs = qs.filter(statut_dossier_id=dossier_id)
        elif dossier_code:
            qs = qs.filter(statut_dossier__code=dossier_code)

        if has_jurist == "avec":
            qs = qs.filter(has_jurist=True)
        elif has_jurist == "sans":
            qs = qs.filter(has_jurist=False)

        if has_conseille == "avec":
            qs = qs.filter(has_conseiller=True)
        elif has_conseille == "sans":
            qs = qs.filter(has_conseiller=False)

        # --- Total ---
        total = qs.count()

        # --- KPI FILTRÉS ---
        today = now().date()

        # RDV aujourd'hui (UNIQUEMENT RDV_PLANIFIE et RDV_CONFIRME) parmi les leads FILTRÉS
        rdv_today = qs.filter(
            appointment_date__date=today,
            status__code__in=[RDV_PLANIFIE, RDV_CONFIRME]
        ).count()

        # Contrats aujourd'hui liés aux leads FILTRÉS
        filtered_lead_ids = list(qs.values_list('id', flat=True))
        contracts_today = Contract.objects.filter(
            client__lead_id__in=filtered_lead_ids,
            created_at__date=today
        ).count()

        # --- Pagination & tri ---
        qs = qs.order_by(ordering)
        start = (page - 1) * page_size
        end = start + page_size

        leads = qs[start:end]

        rows = []
        for lead in leads:
            rows.append({
                "id": lead.id,
                "first_name": lead.first_name,
                "last_name": lead.last_name,
                "email": lead.email,
                "phone": lead.phone,
                "created_at": lead.created_at,
                "appointment_date": lead.appointment_date,
                "status_id": lead.status_id,
                "statut_dossier_id": lead.statut_dossier_id,
                "lead_status_code": getattr(lead, "lead_status_code", None),
                "lead_status_label": getattr(lead, "lead_status_label", None),
                "lead_status_color": getattr(lead, "lead_status_color", None),
                "statut_dossier_code": getattr(lead, "statut_dossier_code", None),
                "statut_dossier_label": getattr(lead, "statut_dossier_label", None),
                "statut_dossier_color": getattr(lead, "statut_dossier_color", None),
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

        return Response(
            {
                "total": total,
                "page": page,
                "page_size": page_size,
                "ordering": ordering,
                "items": rows,
                "kpi": {
                    "rdv_today": rdv_today,  # Seulement RDV_PLANIFIE et RDV_CONFIRME
                    "contracts_today": contracts_today,
                },
            }
        )