from datetime import date, datetime, time
from typing import Optional

from django.db.models import Exists, F, OuterRef, Subquery
from django.utils.dateparse import parse_date, parse_datetime
from django.utils.timezone import get_current_timezone, is_naive, make_aware, now
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.leads.models import Lead
from api.contracts.models import Contract
from api.leads.constants import RDV_CONFIRME, RDV_PLANIFIE


# ---------- Utils ----------

def _parse_iso_any(value: Optional[str]) -> Optional[object]:
    if not value:
        return None
    return parse_datetime(value) or parse_date(value)


def _to_aware(value: Optional[object], *, end_of_day: bool = False) -> Optional[datetime]:
    if value is None:
        return None

    tz = get_current_timezone()

    if isinstance(value, date) and not isinstance(value, datetime):
        dt = datetime.combine(
            value,
            time(23, 59, 59, 999999) if end_of_day else time.min
        )
        return make_aware(dt, timezone=tz)

    if is_naive(value):
        return make_aware(value, timezone=tz)

    return value


def _normalize_avec_sans(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    value = value.strip().lower()
    if value in {"avec", "oui", "with", "true", "1"}:
        return "avec"
    if value in {"sans", "non", "without", "false", "0"}:
        return "sans"
    return None


def _to_int_or_none(value: Optional[str]) -> Optional[int]:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


# ---------- View ----------

class LeadSearchView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        params = request.query_params

        # --- Query params ---
        date_from = _to_aware(_parse_iso_any(params.get("date_from")))
        date_to = _to_aware(_parse_iso_any(params.get("date_to")), end_of_day=True)

        appt_from = _to_aware(_parse_iso_any(params.get("appt_from")))
        appt_to = _to_aware(_parse_iso_any(params.get("appt_to")), end_of_day=True)

        status_code = params.get("status_code")
        status_id = _to_int_or_none(params.get("status_id"))

        dossier_code = params.get("dossier_code")
        dossier_id = _to_int_or_none(params.get("dossier_id"))

        has_jurist = _normalize_avec_sans(params.get("has_jurist"))
        has_conseiller = _normalize_avec_sans(params.get("has_conseiller"))

        # --- Pagination ---
        page = max(_to_int_or_none(params.get("page")) or 1, 1)
        page_size = min(max(_to_int_or_none(params.get("page_size")) or 20, 1), 200)

        ordering = params.get("ordering", "-created_at")
        if ordering not in {
            "created_at", "-created_at",
            "appointment_date", "-appointment_date",
            "id", "-id",
        }:
            ordering = "-created_at"

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

        # --- Filters ---
        if date_from:
            qs = qs.filter(created_at__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__lte=date_to)

        if appt_from:
            qs = qs.filter(appointment_date__gte=appt_from)
        if appt_to:
            qs = qs.filter(appointment_date__lte=appt_to)

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

        if has_conseiller == "avec":
            qs = qs.filter(has_conseiller=True)
        elif has_conseiller == "sans":
            qs = qs.filter(has_conseiller=False)

        # --- Snapshot filtré (AVANT pagination) ---
        filtered_qs = qs

        total = filtered_qs.count()

        # --- KPI ---
        today = now()
        start_today = today.replace(hour=0, minute=0, second=0, microsecond=0)
        end_today = today.replace(hour=23, minute=59, second=59, microsecond=999999)

        rdv_today = filtered_qs.filter(
            appointment_date__range=(start_today, end_today),
            status__code__in=[RDV_PLANIFIE, RDV_CONFIRME],
        ).count()

        contracts_today = Contract.objects.filter(
            client__lead_id__in=Subquery(filtered_qs.values("id")),
            created_at__range=(start_today, end_today),
        ).count()

        # --- Pagination ---
        qs = filtered_qs.order_by(ordering)
        start = (page - 1) * page_size
        end = start + page_size

        leads = qs[start:end]

        items = [
            {
                "id": lead.id,
                "first_name": lead.first_name,
                "last_name": lead.last_name,
                "email": lead.email,
                "phone": lead.phone,
                "created_at": lead.created_at,
                "appointment_date": lead.appointment_date,
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
            }
            for lead in leads
        ]

        return Response(
            {
                "total": total,
                "page": page,
                "page_size": page_size,
                "ordering": ordering,
                "items": items,
                "kpi": {
                    "rdv_today": rdv_today,
                    "contracts_today": contracts_today,
                },
            }
        )
