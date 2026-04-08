from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone

from api.leads.models import Lead


class LeadStatsTodayView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.localdate()
        user  = request.user

        all_leads = Lead.objects.all()

        # ── Total leads
        total_leads = all_leads.count()

        # ── RDV confirmés aujourd'hui
        rdv_confirme_today = all_leads.filter(
            appointment_date__date=today,
            status__code__in=["RDV_CONFIRME", "CONFIRME"],
        ).count()

        # ── RDV à confirmer aujourd'hui
        rdv_a_confirmer_today = all_leads.filter(
            appointment_date__date=today,
            status__code__in=["RDV_A_CONFIRMER", "A_CONFIRMER"],
        ).count()

        # ── Présents aujourd'hui
        presents_today = all_leads.filter(
            appointment_date__date=today,
            status__code__in=["PRESENT", "RDV_PRESENT"],
        ).count()

        # 🔥 Absents aujourd'hui
        # Un lead est "absent" s'il avait un RDV aujourd'hui et que son statut
        # indique qu'il ne s'est pas présenté (ABSENT, NON_PRESENT, NO_SHOW, etc.)
        absents_today = all_leads.filter(
            appointment_date__date=today,
            status__code__in=["ABSENT", "NON_PRESENT", "NO_SHOW", "RDV_ABSENT"],
        ).count()

        # ── Tâches du jour assignées à l'utilisateur courant
        tasks_today = all_leads.filter(
            tasks__due_at__date=today,
            tasks__completed_at__isnull=True,
            tasks__assigned_to=user,
        ).distinct().count()

        # ── Tâches en retard assignées à l'utilisateur courant
        total_overdue_tasks = all_leads.filter(
            tasks__due_at__date__lt=today,
            tasks__completed_at__isnull=True,
            tasks__assigned_to=user,
        ).distinct().count()

        return Response({
            "total_leads":           total_leads,
            "rdv_confirme_today":    rdv_confirme_today,
            "rdv_a_confirmer_today": rdv_a_confirmer_today,
            "presents_today":        presents_today,
            "absents_today":         absents_today,      # 🔥 NOUVEAU
            "tasks_today":           tasks_today,
            "total_overdue_tasks":   total_overdue_tasks,
        })