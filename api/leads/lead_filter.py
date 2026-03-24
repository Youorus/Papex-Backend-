from rest_framework import generics, permissions
from rest_framework.filters import OrderingFilter
from django.db.models import Q, Count
from django.utils import timezone

from api.core.pagination import CRMLeadPagination
from api.leads.models import Lead
from api.leads.serializers import LeadSerializer


class LeadFilterView(generics.ListAPIView):

    serializer_class = LeadSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = CRMLeadPagination

    # 🔥 ajout du tri DRF
    filter_backends = [OrderingFilter]
    ordering_fields = ["appointment_date", "created_at"]
    ordering = ["-created_at"]  # fallback

    def get_queryset(self):

        p = self.request.query_params

        qs = (
            Lead.objects
            .select_related(
                "status",
                "statut_dossier",
                "statut_dossier_interne",
            )
            .prefetch_related(
                "assigned_to",
                "jurist_assigned",
            )
        )

        # ── Date création
        created_from = p.get("created_from")
        created_to = p.get("created_to")

        if created_from:
            qs = qs.filter(created_at__date__gte=created_from)

        if created_to:
            qs = qs.filter(created_at__date__lte=created_to)

        # ── Date rendez-vous
        appt_from = p.get("appointment_from")
        appt_to = p.get("appointment_to")

        if appt_from:
            qs = qs.filter(appointment_date__date__gte=appt_from)

        if appt_to:
            qs = qs.filter(appointment_date__date__lte=appt_to)

        # ── Type RDV
        appt_type = p.get("appointment_type")
        if appt_type:
            qs = qs.filter(appointment_type=appt_type)

        # ── Statut lead
        status_ids = p.getlist("status")
        if status_ids:
            qs = qs.filter(status_id__in=status_ids)

        # ── Statut dossier
        dossier_status = p.get("dossier_status")
        if dossier_status:
            qs = qs.filter(statut_dossier_id=dossier_status)

        # ── Juriste
        jurist_id = p.get("jurist_id")
        if jurist_id:
            qs = qs.filter(jurist_assigned__id=jurist_id)

        # ── Conseiller
        advisor_id = p.get("advisor_id")
        if advisor_id:
            qs = qs.filter(assigned_to__id=advisor_id)

        # ── Tâches
        has_tasks = p.get("has_tasks")

        if has_tasks == "true":
            qs = qs.filter(tasks__isnull=False).distinct()

        elif has_tasks == "false":
            qs = qs.filter(tasks__isnull=True)

        task_due_from = p.get("task_due_from")
        task_due_to = p.get("task_due_to")

        if task_due_from or task_due_to:

            task_q = Q()

            if task_due_from:
                task_q &= Q(tasks__due_at__date__gte=task_due_from)

            if task_due_to:
                task_q &= Q(tasks__due_at__date__lte=task_due_to)

            qs = qs.filter(task_q).distinct()

        # 🔥 TRI FINAL
        ordering = p.get("ordering")

        if ordering:
            qs = qs.order_by(ordering)
        else:
            # 👉 tri par heure de RDV par défaut
            qs = qs.order_by("appointment_date", "-created_at")

        return qs

    def list(self, request, *args, **kwargs):

        qs = self.get_queryset()

        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page, many=True)
        response = self.get_paginated_response(serializer.data)

        # ── Aggregates

        by_status_raw = (
            qs.values("status__id", "status__label", "status__color")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        by_status = [
            {
                "id": row["status__id"],
                "label": row["status__label"] or "—",
                "color": row["status__color"] or "#888",
                "count": row["count"],
            }
            for row in by_status_raw
        ]

        by_appt_raw = (
            qs.exclude(appointment_type__isnull=True)
            .exclude(appointment_type="")
            .values("appointment_type")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        by_appointment_type = [
            {
                "type": row["appointment_type"],
                "count": row["count"],
            }
            for row in by_appt_raw
        ]

        total_with_tasks = qs.filter(tasks__isnull=False).distinct().count()

        now = timezone.now()

        total_overdue_tasks = qs.filter(
            tasks__due_at__lt=now,
            tasks__completed_at__isnull=True,
        ).distinct().count()

        response.data["aggregates"] = {
            "by_status": by_status,
            "by_appointment_type": by_appointment_type,
            "total_with_tasks": total_with_tasks,
            "total_overdue_tasks": total_overdue_tasks,
        }

        return response