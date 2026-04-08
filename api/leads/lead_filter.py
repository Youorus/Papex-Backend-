from rest_framework import generics, permissions
from django.db.models import (
    Count, Exists, OuterRef,
    Case, When, F,
    DateTimeField, IntegerField,
    Q,
)
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
        user = self.request.user

        qs = (
            Lead.objects
            .select_related("status", "statut_dossier", "statut_dossier_interne")
            .prefetch_related("assigned_to")
        )

        # ── 1. Filtres simples sur le Lead ──────────────────────────────────
        if p.get("created_from"):
            qs = qs.filter(created_at__date__gte=p.get("created_from"))
        if p.get("created_to"):
            qs = qs.filter(created_at__date__lte=p.get("created_to"))

        if p.getlist("status"):
            # Nettoyage pour éviter les listes vides types ['']
            st_ids = [id for id in p.getlist("status") if id]
            if st_ids:
                qs = qs.filter(status_id__in=st_ids)

        if p.getlist("assigned_to"):
            as_ids = [id for id in p.getlist("assigned_to") if id]
            if as_ids:
                qs = qs.filter(assigned_to__id__in=as_ids).distinct()

        # ── 2. Annotation de base (pour les agrégats de la méthode list) ─────
        qs = qs.annotate(
            has_tasks=Exists(
                LeadTask.objects.filter(
                    lead=OuterRef("pk"),
                    assigned_to=user,
                    completed_at__isnull=True,
                )
            ),
            has_contract=Exists(
                Contract.objects.filter(client__lead=OuterRef("pk"))
            ),
        )

        # ── 3. Logique avancée des tâches ────────────────────────────────────

        # On récupère et on nettoie les listes pour éviter les filtres vides qui cassent tout
        t_status = [v for v in p.getlist("task_status") if v]
        t_priority = [v for v in p.getlist("task_priority") if v]
        t_assigned = [v for v in p.getlist("task_assigned_to") if v]
        t_creators = [v for v in p.getlist("task_created_by") if v]

        t_due_from = p.get("task_due_from")
        t_due_to = p.get("task_due_to")
        t_resch_min = p.get("task_reschedule_min")
        t_resch_max = p.get("task_reschedule_max")

        has_tasks_param = p.get("has_tasks")  # "true" | "false"

        # On détermine si on doit appliquer un filtrage par tâche
        has_task_filters = any([
            t_due_from, t_due_to, t_status, t_priority,
            t_assigned, t_creators, t_resch_min, t_resch_max
        ])

        if has_tasks_param == "false":
            # Leads qui n'ont AUCUNE tâche active pour l'utilisateur
            qs = qs.filter(has_tasks=False)

        elif has_tasks_param == "true" and not has_task_filters:
            # Mode CRM classique : seulement les tâches actives de l'utilisateur
            qs = qs.filter(has_tasks=True)

        elif has_task_filters or has_tasks_param == "true":
            # RECHERCHE AVANCÉE : on construit le sous-queryset dynamiquement
            task_qs = LeadTask.objects.filter(lead=OuterRef("pk"))

            if t_due_from:
                task_qs = task_qs.filter(due_at__date__gte=t_due_from)
            if t_due_to:
                task_qs = task_qs.filter(due_at__date__lte=t_due_to)

            if t_status:
                task_qs = task_qs.filter(status__in=t_status)
            elif has_tasks_param == "true":
                # Si on demande "Avec tâches" sans préciser de statut,
                # on filtre par défaut sur les non-terminées
                task_qs = task_qs.filter(completed_at__isnull=True)

            if t_priority:
                task_qs = task_qs.filter(priority__in=t_priority)

            if t_assigned:
                task_qs = task_qs.filter(assigned_to__id__in=t_assigned)

            # --- LES FILTRES QUI MANQUAIENT ---
            if t_creators:
                task_qs = task_qs.filter(created_by__id__in=t_creators)

            if t_resch_min:
                task_qs = task_qs.filter(reschedule_count__gte=t_resch_min)

            if t_resch_max:
                task_qs = task_qs.filter(reschedule_count__lte=t_resch_max)

            # Application du filtre final
            qs = qs.annotate(has_tasks_filtered=Exists(task_qs)).filter(has_tasks_filtered=True)

        # ── 4. Tri CRM ───────────────────────────────────────────────────────
        qs = qs.annotate(
            has_appointment=Case(When(appointment_date__isnull=False, then=0), default=1, output_field=IntegerField()),
            sort_date=Case(When(appointment_date__isnull=False, then=F("appointment_date")), default=F("created_at"),
                           output_field=DateTimeField())
        ).order_by("has_appointment", "sort_date", "-created_at")

        return qs

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page, many=True)
        response = self.get_paginated_response(serializer.data)

        # Agrégats
        by_status = [
            {"id": r["status__id"], "label": r["status__label"] or "—", "color": r["status__color"] or "#888",
             "count": r["count"]}
            for r in
            qs.values("status__id", "status__label", "status__color").annotate(count=Count("id")).order_by("-count")
        ]

        total_with_tasks = qs.filter(has_tasks=True).count()
        now = timezone.now()
        total_overdue = qs.annotate(
            overdue=Exists(LeadTask.objects.filter(lead=OuterRef("pk"), completed_at__isnull=True, due_at__lt=now,
                                                   assigned_to=request.user))
        ).filter(overdue=True).count()

        response.data["aggregates"] = {
            "by_status": by_status,
            "total_with_tasks": total_with_tasks,
            "total_overdue_tasks": total_overdue,
        }
        return response