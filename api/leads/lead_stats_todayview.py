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

        # 🔥 TOTAL LEADS
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

        return Response({
            "total_leads": total_leads,
            "rdv_confirme_today": rdv_confirme_today,
            "rdv_a_confirmer_today": rdv_a_confirmer_today,
            "presents_today": presents_today,
            "tasks_today": tasks_today,
            "total_overdue_tasks": total_overdue_tasks,
        })