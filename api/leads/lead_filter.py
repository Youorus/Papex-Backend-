from rest_framework import generics, permissions
from django.db.models import Q, Count, Exists, OuterRef
from django.utils import timezone

from api.core.pagination import CRMLeadPagination
from api.leads.models import Lead
from api.leads.serializers import LeadSerializer
from api.contracts.models import Contract
from api.leads_task.models import LeadTask


class LeadFilterView(generics.ListAPIView):
    serializer_class = LeadSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = CRMLeadPagination

    def get_queryset(self):
        p = self.request.query_params

        qs = (
            Lead.objects
            .select_related(
                "status",
                "statut_dossier",
                "statut_dossier_interne",
            )
            .prefetch_related("assigned_to")
        )

        # ───────────────────────
        # 📅 Dates
        # ───────────────────────

        if p.get("created_from"):
            qs = qs.filter(created_at__date__gte=p.get("created_from"))

        if p.get("created_to"):
            qs = qs.filter(created_at__date__lte=p.get("created_to"))

        if p.get("appointment_from"):
            qs = qs.filter(appointment_date__date__gte=p.get("appointment_from"))

        if p.get("appointment_to"):
            qs = qs.filter(appointment_date__date__lte=p.get("appointment_to"))

        # ───────────────────────
        # 📌 Champs simples
        # ───────────────────────

        if p.get("appointment_type"):
            qs = qs.filter(appointment_type=p.get("appointment_type"))

        if p.getlist("status"):
            qs = qs.filter(status_id__in=p.getlist("status"))

        if p.get("dossier_status"):
            qs = qs.filter(statut_dossier_id=p.get("dossier_status"))

        if p.get("assigned_to"):
            qs = qs.filter(assigned_to__id=p.get("assigned_to"))

        # ───────────────────────
        # 🧠 EXISTS (CRUCIAL)
        # ───────────────────────

        qs = qs.annotate(
            has_tasks=Exists(
                LeadTask.objects.filter(lead=OuterRef("pk"))
            ),
            has_contract=Exists(
                Contract.objects.filter(client__lead=OuterRef("pk"))
            ),
        )

        # ───────────────────────
        # ✅ Filtre tâches (clean)
        # ───────────────────────

        has_tasks = p.get("has_tasks")

        if has_tasks == "true":
            qs = qs.filter(has_tasks=True)

        elif has_tasks == "false":
            qs = qs.filter(has_tasks=False)

        # 📅 Filtre échéance tâche (SANS JOIN)
        if p.get("task_due_from") or p.get("task_due_to"):

            task_filters = {"lead": OuterRef("pk")}

            if p.get("task_due_from"):
                task_filters["due_at__date__gte"] = p.get("task_due_from")

            if p.get("task_due_to"):
                task_filters["due_at__date__lte"] = p.get("task_due_to")

            qs = qs.annotate(
                has_filtered_tasks=Exists(
                    LeadTask.objects.filter(**task_filters)
                )
            ).filter(has_filtered_tasks=True)

        # ───────────────────────
        # 📄 Filtre contrats
        # ───────────────────────

        has_contract = p.get("has_contract")

        if has_contract == "true":
            qs = qs.filter(has_contract=True)

        elif has_contract == "false":
            qs = qs.filter(has_contract=False)

        # 👤 Créateur du contrat
        if p.get("contract_created_by"):
            qs = qs.annotate(
                contract_by_user=Exists(
                    Contract.objects.filter(
                        client__lead=OuterRef("pk"),
                        created_by_id=p.get("contract_created_by"),
                    )
                )
            ).filter(contract_by_user=True)

        return qs.order_by("-created_at")

    # ───────────────────────
    # 📊 LIST + AGGREGATES
    # ───────────────────────

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()

        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page, many=True)

        response = self.get_paginated_response(serializer.data)

        # ───────────────────────
        # 📊 Aggregates
        # ───────────────────────

        # 🟢 Par statut
        by_status = list(
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
            for row in by_status
        ]

        # 🟣 Par type de RDV
        by_appointment_type = list(
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
            for row in by_appointment_type
        ]

        # 🔵 Totaux tâches (SANS JOIN)
        total_with_tasks = qs.filter(has_tasks=True).count()

        now = timezone.now()

        total_overdue_tasks = qs.annotate(
            has_overdue_tasks=Exists(
                LeadTask.objects.filter(
                    lead=OuterRef("pk"),
                    completed_at__isnull=True,
                    due_at__lt=now,
                )
            )
        ).filter(has_overdue_tasks=True).count()

        response.data["aggregates"] = {
            "by_status": by_status,
            "by_appointment_type": by_appointment_type,
            "total_with_tasks": total_with_tasks,
            "total_overdue_tasks": total_overdue_tasks,
        }

        return response