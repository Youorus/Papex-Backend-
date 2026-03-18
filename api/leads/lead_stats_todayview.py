from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Count
from django.utils import timezone

from api.leads.models import Lead


class LeadStatsTodayView(APIView):
    """
    GET /api/leads/stats-today/

    Retourne les statistiques du jour, indépendantes de tout filtre.
    Utilisé par les cards "par défaut" du dashboard leads.

    Répond toujours avec les données fraîches de la journée en cours.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.localdate()
        now   = timezone.now()

        all_leads = Lead.objects.all()

        # ── RDV confirmés aujourd'hui ─────────────────────────────────────────
        # Leads dont le rendez-vous est aujourd'hui ET dont le statut indique
        # une confirmation. Adaptez le filtre status__code selon vos valeurs réelles.
        # Exemples courants : "RDV_CONFIRME", "CONFIRME", "CONFIRMED"
        rdv_confirme_today = all_leads.filter(
            appointment_date__date=today,
            status__code__in=["RDV_CONFIRME", "CONFIRME", "CONFIRMED"],
        ).count()

        # ── RDV à confirmer aujourd'hui ───────────────────────────────────────
        # Leads dont le rendez-vous est aujourd'hui ET dont le statut indique
        # qu'il reste à confirmer.
        # Exemples courants : "RDV_A_CONFIRMER", "A_CONFIRMER"
        rdv_a_confirmer_today = all_leads.filter(
            appointment_date__date=today,
            status__code__in=["RDV_A_CONFIRMER", "A_CONFIRMER"],
        ).count()

        # ── Tâches du jour (non complétées) ──────────────────────────────────
        tasks_today = all_leads.filter(
            tasks__due_at__date=today,
            tasks__completed_at__isnull=True,
        ).distinct().count()

        # ── Tâches en retard (toutes dates) ──────────────────────────────────
        total_overdue_tasks = all_leads.filter(
            tasks__due_at__lt=now,
            tasks__completed_at__isnull=True,
        ).distinct().count()

        return Response({
            "rdv_confirme_today":   rdv_confirme_today,
            "rdv_a_confirmer_today": rdv_a_confirmer_today,
            "tasks_today":          tasks_today,
            "total_overdue_tasks":  total_overdue_tasks,
        })