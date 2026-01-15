# api/leads/views.py

from django.db import transaction
from django.db.models import F, Q, Count
from django.utils.dateparse import parse_date
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status as drf_status, viewsets, filters
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from api.booking.models import SlotQuota
from api.lead_status.models import LeadStatus
from api.leads.constants import RDV_CONFIRME, RDV_A_CONFIRMER, A_RAPPELER, ABSENT
from api.leads.models import Lead
from api.leads.permissions import IsLeadCreator, IsConseillerOrAdmin
from api.leads.serializers import LeadSerializer
from api.sms.tasks import send_appointment_confirmation_sms_task
from api.users.models import User
from api.users.roles import UserRoles

from api.utils.email.leads.tasks import (
    send_appointment_confirmation_task,
    send_dossier_status_notification_task,
    send_formulaire_task,
    send_jurist_assigned_notification_task,
)


class LeadViewSet(viewsets.ModelViewSet):
    """
    ViewSet optimisé pour la gestion des leads.
    """
    serializer_class = LeadSerializer
    permission_classes = [IsLeadCreator]

    # Configuration des filtres standards (remplace tes méthodes manuelles)
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = {
        'status__code': ['exact'],  # ex: RDV_CONFIRME
        'appointment_type': ['exact'],
        'appointment_date': ['exact', 'date'],  # appointment_date__date=YYYY-MM-DD
        'created_at': ['date'],  # created_at__date=YYYY-MM-DD
    }
    search_fields = [
        'first_name',
        'last_name',
        'phone',
        'email',
    ]
    ordering_fields = [
        'created_at',
        'appointment_date',
    ]
    ordering = ['-created_at']

    # =====================
    # QUERYSET OPTIMISÉ
    # =====================

    def get_queryset(self):
        """
        Queryset optimisé + filtrage par rôle utilisateur.
        - select_related : FK
        - prefetch_related : M2M
        - évite N+1
        - garantit que chaque utilisateur ne voit QUE ses leads
        """
        qs = Lead.objects.select_related(
            'status',
            'statut_dossier',
            'statut_dossier_interne',
        ).prefetch_related(
            'assigned_to',
            'jurist_assigned',
        )

        user = self.request.user

        # 🔒 Sécurité métier par rôle
        if user.role == UserRoles.CONSEILLER:
            qs = qs.filter(assigned_to=user)

        elif user.role == UserRoles.JURISTE:
            qs = qs.filter(jurist_assigned=user)

        # ADMIN & ACCUEIL → accès global
        return qs

    # =====================
    # PERMISSIONS
    # =====================

    def get_permissions(self):
        if self.action == "public_create":
            return [AllowAny()]
        if self.action in ["assignment", "assign_juristes"]:
            return [IsConseillerOrAdmin()]
        return super().get_permissions()

    # =====================
    # LOGIQUE DE CRÉATION / NOTIFICATION
    # =====================

    def perform_create(self, serializer):
        lead = serializer.save(status=self._get_default_status())
        self._send_notifications(lead)

    def perform_update(self, serializer):
        before = self.get_object()
        after = serializer.save()

        # Détection des changements pour déclencher les tâches Celery
        status_changed = before.status_id != after.status_id
        appointment_changed = before.appointment_date != after.appointment_date
        dossier_changed = getattr(before.statut_dossier, 'id', None) != getattr(after.statut_dossier, 'id', None)

        if status_changed or appointment_changed:
            self._send_notifications(after)

        if dossier_changed and after.statut_dossier:
            send_dossier_status_notification_task.delay(after.id)

    def _get_default_status(self):
        try:
            return LeadStatus.objects.get(code=RDV_A_CONFIRMER)
        except LeadStatus.DoesNotExist:
            raise NotFound("Le statut RDV_A_CONFIRMER n'existe pas.")

    def _send_notifications(self, lead):
        """Centralisation des envois asynchrones."""
        if getattr(lead.status, "code", None) != RDV_A_CONFIRMER:
            return
        if lead.email:
            send_appointment_confirmation_task.delay(lead.id)
        if lead.phone:
            send_appointment_confirmation_sms_task.delay(lead.id)

    # =====================
    # ROUTES PERSONNALISÉES
    # =====================

    @action(detail=False, methods=["post"], url_path="public-create", permission_classes=[AllowAny])
    def public_create(self, request):
        """Création publique avec gestion de quota sécurisée (Atomic + Lock)."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        appt_dt = serializer.validated_data.get("appointment_date")
        if not appt_dt:
            raise ValidationError({"appointment_date": "Champ requis."})

        with transaction.atomic():
            # select_for_update() empêche deux requêtes de modifier le même quota en même temps
            quota, _ = SlotQuota.objects.select_for_update().get_or_create(
                start_at=appt_dt,
                defaults={"capacity": 1, "booked": 0},
            )

            if quota.booked >= quota.capacity:
                return Response(
                    {"detail": "Créneau complet."},
                    status=drf_status.HTTP_409_CONFLICT
                )

            quota.booked += 1
            quota.save()

            lead = serializer.save(status=self._get_default_status())

        self._send_notifications(lead)
        return Response(serializer.data, status=drf_status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], url_path="count-by-status")
    def count_by_status(self, request):
        """Stats optimisées en une seule requête SQL GROUP BY."""
        codes = [RDV_A_CONFIRMER, A_RAPPELER, RDV_CONFIRME, ABSENT]

        # On compte directement en base de données
        stats = (
            Lead.objects.filter(status__code__in=codes)
            .values('status__code')
            .annotate(total=Count('id'))
        )

        # On prépare le dictionnaire de réponse
        results = {code: 0 for code in codes}
        for s in stats:
            results[s['status__code']] = s['total']

        return Response(results)

    @action(detail=True, methods=["patch"], url_path="assignment")
    def assignment(self, request, pk=None):
        lead = self.get_object()
        user = request.user

        action_type = request.data.get("action")  # 'assign' ou 'unassign'

        if user.role == UserRoles.ADMIN:
            # Gestion Admin (assignation multiple)
            assign_ids = request.data.get("assign", [])
            unassign_ids = request.data.get("unassign", [])

            if assign_ids:
                users = User.objects.filter(id__in=assign_ids, role=UserRoles.CONSEILLER, is_active=True)
                lead.assigned_to.add(*users)
            if unassign_ids:
                lead.assigned_to.remove(*User.objects.filter(id__in=unassign_ids))
        else:
            # Gestion Conseiller (auto-assignation)
            if action_type == "assign":
                lead.assigned_to.add(user)
            else:
                lead.assigned_to.remove(user)

        return Response(self.get_serializer(lead).data)

    @action(detail=True, methods=["patch"], url_path="assign-juristes")
    def assign_juristes(self, request, pk=None):
        if request.user.role != UserRoles.ADMIN:
            raise PermissionDenied("Admin requis.")

        lead = self.get_object()
        assign_ids = request.data.get("assign", [])

        if assign_ids:
            juristes = User.objects.filter(id__in=assign_ids, role=UserRoles.JURISTE, is_active=True)
            lead.jurist_assigned.add(*juristes)

            if lead.email and juristes.exists():
                send_jurist_assigned_notification_task.delay(lead.id, juristes.first().id)

        unassign_ids = request.data.get("unassign", [])
        if unassign_ids:
            lead.jurist_assigned.remove(*User.objects.filter(id__in=unassign_ids))

        return Response(self.get_serializer(lead).data)

    @action(detail=True, methods=["post"], url_path="send-formulaire-email")
    def send_formulaire_email(self, request, pk=None):
        lead = self.get_object()
        send_formulaire_task.delay(lead.id)
        return Response({"detail": "E-mail envoyé."})