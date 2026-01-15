# api/leads/views.py

from django.db import transaction
from django.db.models import F, Q, Count
from django.utils.dateparse import parse_date
from django_filters import rest_framework as filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status as drf_status, viewsets
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


# =====================
# FILTRE PERSONNALISÉ
# =====================

class LeadFilter(filters.FilterSet):
    """
    Filtre personnalisé pour les leads.
    Permet de filtrer par statut, date de création, date de RDV et recherche textuelle.
    """
    status_code = filters.CharFilter(
        field_name='status__code',
        lookup_expr='exact',
        help_text="Code du statut (ex: RDV_CONFIRME)"
    )
    created_date = filters.DateFilter(
        field_name='created_at',
        lookup_expr='date',
        help_text="Date de création (format: YYYY-MM-DD)"
    )
    appointment_date = filters.DateFilter(
        field_name='appointment_date',
        lookup_expr='date',
        help_text="Date du rendez-vous (format: YYYY-MM-DD)"
    )
    search = filters.CharFilter(
        method='filter_search',
        help_text="Recherche sur nom, prénom, téléphone, email (min 2 caractères)"
    )

    def filter_search(self, queryset, name, value):
        """
        Recherche personnalisée sur plusieurs champs.
        Ignore les recherches < 2 caractères.
        """
        if not value or len(value.strip()) < 2:
            return queryset

        search_value = value.strip()
        return queryset.filter(
            Q(first_name__icontains=search_value) |
            Q(last_name__icontains=search_value) |
            Q(phone__icontains=search_value) |
            Q(email__icontains=search_value)
        )

    class Meta:
        model = Lead
        fields = ['status_code', 'created_date', 'appointment_date', 'search']


# =====================
# VIEWSET PRINCIPAL
# =====================

class LeadViewSet(viewsets.ModelViewSet):
    """
    ViewSet optimisé pour la gestion des leads.

    Fonctionnalités :
    - CRUD complet avec permissions par rôle
    - Filtrage avancé (statut, date, recherche)
    - Pagination automatique
    - Endpoints personnalisés (assignation, stats, etc.)
    - Notifications asynchrones (email + SMS)
    """
    serializer_class = LeadSerializer
    permission_classes = [IsLeadCreator]

    # Configuration des filtres
    filter_backends = [
        DjangoFilterBackend,
        filters.OrderingFilter,
    ]
    filterset_class = LeadFilter
    ordering_fields = ['created_at', 'appointment_date']
    ordering = ['-created_at']

    # =====================
    # QUERYSET OPTIMISÉ
    # =====================

    def get_queryset(self):
        """
        Queryset optimisé avec select_related et prefetch_related.
        Évite les requêtes N+1.
        """
        qs = Lead.objects.select_related(
            'status',
            'statut_dossier',
            'statut_dossier_interne',
        ).prefetch_related(
            'assigned_to',
            'jurist_assigned',
        )

        # Les permissions de filtrage par utilisateur sont gérées
        # dans IsLeadCreator, donc on retourne le queryset complet ici
        return qs

    # =====================
    # PERMISSIONS
    # =====================

    def get_permissions(self):
        """
        Définit les permissions selon l'action.
        """
        if self.action == "public_create":
            return [AllowAny()]
        if self.action in ["assignment", "assign_juristes"]:
            return [IsConseillerOrAdmin()]
        return super().get_permissions()

    # =====================
    # LOGIQUE DE CRÉATION / MISE À JOUR
    # =====================

    def perform_create(self, serializer):
        """
        Création d'un lead avec statut par défaut et notifications.
        """
        lead = serializer.save(status=self._get_default_status())
        self._send_notifications(lead)

    def perform_update(self, serializer):
        """
        Mise à jour avec détection des changements pour notifications.
        """
        before = self.get_object()
        after = serializer.save()

        # Détection des changements critiques
        status_changed = before.status_id != after.status_id
        appointment_changed = before.appointment_date != after.appointment_date
        dossier_changed = (
                getattr(before.statut_dossier, 'id', None) !=
                getattr(after.statut_dossier, 'id', None)
        )

        # Notifications conditionnelles
        if status_changed or appointment_changed:
            self._send_notifications(after)

        if dossier_changed and after.statut_dossier:
            send_dossier_status_notification_task.delay(after.id)

    def _get_default_status(self):
        """
        Récupère le statut par défaut pour les nouveaux leads.
        """
        try:
            return LeadStatus.objects.get(code=RDV_A_CONFIRMER)
        except LeadStatus.DoesNotExist:
            raise NotFound("Le statut RDV_A_CONFIRMER n'existe pas.")

    def _send_notifications(self, lead):
        """
        Centralisation des envois asynchrones (email + SMS).
        Uniquement pour les leads avec statut RDV_A_CONFIRMER.
        """
        if getattr(lead.status, "code", None) != RDV_A_CONFIRMER:
            return

        if lead.email:
            send_appointment_confirmation_task.delay(lead.id)
        if lead.phone:
            send_appointment_confirmation_sms_task.delay(lead.id)

    # =====================
    # ROUTES PERSONNALISÉES
    # =====================

    @action(
        detail=False,
        methods=["post"],
        url_path="public-create",
        permission_classes=[AllowAny]
    )
    def public_create(self, request):
        """
        Création publique d'un lead avec gestion de quota sécurisée.
        Utilise une transaction atomique avec verrou pour éviter les double-bookings.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        appt_dt = serializer.validated_data.get("appointment_date")
        if not appt_dt:
            raise ValidationError({"appointment_date": "Ce champ est requis."})

        with transaction.atomic():
            # select_for_update() verrouille la ligne pendant la transaction
            quota, _ = SlotQuota.objects.select_for_update().get_or_create(
                start_at=appt_dt,
                defaults={"capacity": 1, "booked": 0},
            )

            if quota.booked >= quota.capacity:
                return Response(
                    {"detail": "Ce créneau est complet."},
                    status=drf_status.HTTP_409_CONFLICT
                )

            quota.booked = F('booked') + 1
            quota.save(update_fields=['booked'])

            lead = serializer.save(status=self._get_default_status())

        self._send_notifications(lead)
        return Response(serializer.data, status=drf_status.HTTP_201_CREATED)

    @action(
        detail=False,
        methods=["get"],
        url_path="count-by-status"
    )
    def count_by_status(self, request):
        """
        Statistiques optimisées : compte les leads par statut en une seule requête SQL.

        Retourne un dictionnaire avec les codes de statut comme clés.
        Exemple : {"RDV_CONFIRME": 42, "A_RAPPELER": 15, ...}
        """
        codes = [RDV_A_CONFIRMER, A_RAPPELER, RDV_CONFIRME, ABSENT]

        # Une seule requête SQL avec GROUP BY
        stats = (
            Lead.objects
            .filter(status__code__in=codes)
            .values('status__code')
            .annotate(total=Count('id'))
        )

        # Initialisation avec zéros pour tous les statuts
        results = {code: 0 for code in codes}

        # Remplissage avec les valeurs réelles
        for stat in stats:
            results[stat['status__code']] = stat['total']

        return Response(results)

    @action(
        detail=True,
        methods=["patch"],
        url_path="assignment"
    )
    def assignment(self, request, pk=None):
        """
        Assignation de conseillers à un lead.

        - ADMIN : peut assigner/désassigner plusieurs conseillers
        - CONSEILLER : peut s'auto-assigner/désassigner uniquement

        Body attendu :
        - Pour admin : {"assign": [1, 2], "unassign": [3]}
        - Pour conseiller : {"action": "assign"} ou {"action": "unassign"}
        """
        lead = self.get_object()
        user = request.user

        if user.role == UserRoles.ADMIN:
            # Gestion Admin : assignation multiple
            assign_ids = request.data.get("assign", [])
            unassign_ids = request.data.get("unassign", [])

            if assign_ids:
                users = User.objects.filter(
                    id__in=assign_ids,
                    role=UserRoles.CONSEILLER,
                    is_active=True
                )
                lead.assigned_to.add(*users)

            if unassign_ids:
                lead.assigned_to.remove(
                    *User.objects.filter(id__in=unassign_ids)
                )
        else:
            # Gestion Conseiller : auto-assignation uniquement
            action_type = request.data.get("action")
            if action_type == "assign":
                lead.assigned_to.add(user)
            elif action_type == "unassign":
                lead.assigned_to.remove(user)

        return Response(self.get_serializer(lead).data)

    @action(
        detail=True,
        methods=["patch"],
        url_path="assign-juristes"
    )
    def assign_juristes(self, request, pk=None):
        """
        Assignation de juristes à un lead (réservé aux admins).
        Envoie une notification email au premier juriste assigné.

        Body attendu : {"assign": [1, 2], "unassign": [3]}
        """
        if request.user.role != UserRoles.ADMIN:
            raise PermissionDenied("Seuls les administrateurs peuvent assigner des juristes.")

        lead = self.get_object()
        assign_ids = request.data.get("assign", [])

        if assign_ids:
            juristes = User.objects.filter(
                id__in=assign_ids,
                role=UserRoles.JURISTE,
                is_active=True
            )
            lead.jurist_assigned.add(*juristes)

            # Notification au premier juriste assigné
            if lead.email and juristes.exists():
                send_jurist_assigned_notification_task.delay(
                    lead.id,
                    juristes.first().id
                )

        unassign_ids = request.data.get("unassign", [])
        if unassign_ids:
            lead.jurist_assigned.remove(
                *User.objects.filter(id__in=unassign_ids)
            )

        return Response(self.get_serializer(lead).data)

    @action(
        detail=True,
        methods=["post"],
        url_path="send-formulaire-email"
    )
    def send_formulaire_email(self, request, pk=None):
        """
        Envoie le formulaire par email au lead.
        Tâche asynchrone via Celery.
        """
        lead = self.get_object()
        send_formulaire_task.delay(lead.id)
        return Response(
            {"detail": "L'email contenant le formulaire a été envoyé."},
            status=drf_status.HTTP_200_OK
        )