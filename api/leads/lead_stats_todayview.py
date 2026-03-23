from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone

from api.leads.models import Lead


class LeadStatsTodayView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.localdate()
        now = timezone.now()
        user = request.user

        all_leads = Lead.objects.all()

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

        # Tâches dues AUJOURD'HUI (pas en retard, pas futures)
        tasks_today = all_leads.filter(
            tasks__due_at__date=today,
            tasks__completed_at__isnull=True,
            tasks__assigned_to=user,
        ).distinct().count()

        # Tâches en retard = dues AVANT aujourd'hui, non complétées
        total_overdue_tasks = all_leads.filter(
            tasks__due_at__date__lt=today,   # ← __date__lt=today plutôt que __lt=now
            tasks__completed_at__isnull=True,
            tasks__assigned_to=user,
        ).distinct().count()

        return Response({
            "rdv_confirme_today": rdv_confirme_today,
            "rdv_a_confirmer_today": rdv_a_confirmer_today,
            "presents_today": presents_today,
            "tasks_today": tasks_today,
            "total_overdue_tasks": total_overdue_tasks,
        })