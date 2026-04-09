from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone

from api.leads.models import Lead
from api.leads_task.constants import LeadTaskStatus


class LeadStatsTodayView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.localdate()
        user  = request.user

        all_leads = Lead.objects.all()

        # ─────────────────────────────────────────
        # LEADS
        # ─────────────────────────────────────────

        total_leads = all_leads.count()

        rdv_confirme_today = all_leads.filter(
            appointment_date__date=today,
            status__code__in=["RDV_CONFIRME", "CONFIRME"],
        ).count()

        rdv_a_confirmer_today = all_leads.filter(
            appointment_date__date=today,
            status__code__in=["RDV_A_CONFIRMER", "A_CONFIRMER"],
        ).count()

        presents_today = all_leads.filter(
            appointment_date__date=today,
            status__code__in=["PRESENT", "RDV_PRESENT"],
        ).count()

        # ─────────────────────────────────────────
        # ABSENTS (brut)
        # ─────────────────────────────────────────

        absents_today = all_leads.filter(
            appointment_date__date=today,
            status__code__in=["ABSENT", "NON_PRESENT", "NO_SHOW", "RDV_ABSENT"],
        ).count()

        # ─────────────────────────────────────────
        # 🔥 À RAPPELER (LOGIQUE MÉTIER)
        # ─────────────────────────────────────────

        a_rappeler_today = all_leads.filter(
            tasks__task_type__code="RELANCE_ABSENT",
            tasks__status=LeadTaskStatus.TODO,
            tasks__due_at__date=today,
        ).distinct().count()

        # 🔥 BONUS (optionnel mais recommandé)
        a_rappeler_overdue = all_leads.filter(
            tasks__task_type__code="RELANCE_ABSENT",
            tasks__status=LeadTaskStatus.TODO,
            tasks__due_at__date__lt=today,
        ).distinct().count()

        # ─────────────────────────────────────────
        # TÂCHES UTILISATEUR
        # ─────────────────────────────────────────

        tasks_today = all_leads.filter(
            tasks__due_at__date=today,
            tasks__completed_at__isnull=True,
            tasks__assigned_to=user,
        ).distinct().count()

        total_overdue_tasks = all_leads.filter(
            tasks__due_at__date__lt=today,
            tasks__completed_at__isnull=True,
            tasks__assigned_to=user,
        ).distinct().count()

        # ─────────────────────────────────────────
        # RESPONSE
        # ─────────────────────────────────────────

        return Response({
            "total_leads": total_leads,
            "rdv_confirme_today": rdv_confirme_today,
            "rdv_a_confirmer_today": rdv_a_confirmer_today,
            "presents_today": presents_today,
            "absents_today": absents_today,

            # 🔥 NOUVEAUX KPI
            "a_rappeler_today": a_rappeler_today,
            "a_rappeler_overdue": a_rappeler_overdue,

            "tasks_today": tasks_today,
            "total_overdue_tasks": total_overdue_tasks,
        })