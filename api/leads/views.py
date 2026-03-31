# api/leads/views.py
# ✅ Migré Celery (.delay()) → Django-Q2 (appels directs dispatchers)

from django.db import transaction
from django.db.models import F, Q
from django.utils.dateparse import parse_date
from rest_framework import status as drf_status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from api.booking.models import SlotQuota
from api.lead_status.models import LeadStatus
from api.leads.constants import RDV_CONFIRME, RDV_A_CONFIRMER, A_RAPPELER, ABSENT
from api.leads.models import Lead
from api.leads.permissions import IsLeadCreator, CanAssignLead
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
    serializer_class = LeadSerializer
    permission_classes = [IsLeadCreator]

    # =====================
    # QUERYSET & FILTRES
    # =====================

    def get_queryset(self):
        user = self.request.user

        queryset = Lead.objects.all().prefetch_related(
            "assigned_to",
            "jurist_assigned",
        )

        if user.is_authenticated and user.role == UserRoles.AVOCAT:
            queryset = queryset.filter(assigned_to=user)

        queryset = self._filter_by_search(queryset)
        queryset = self._filter_by_status(queryset)
        queryset = self._filter_by_date(queryset)

        return queryset.order_by("-created_at")

    def _filter_by_search(self, queryset):
        search = self.request.query_params.get("search")
        if search:
            return queryset.filter(
                Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(phone__icontains=search)
                | Q(email__icontains=search)
            )
        return queryset

    def _filter_by_status(self, queryset):
        status_param = self.request.query_params.get("status")
        if status_param and status_param.upper() != "TOUS":
            return queryset.filter(status_id=status_param)
        return queryset

    def _filter_by_date(self, queryset):
        date_str = self.request.query_params.get("date")
        date_field = self.request.query_params.get("date_field", "created_at")
        if date_str:
            parsed_date = parse_date(date_str)
            if parsed_date and date_field in ["created_at", "appointment_date"]:
                return queryset.filter(**{f"{date_field}__date": parsed_date})
        return queryset

    # =====================
    # PERMISSIONS
    # =====================

    def get_permissions(self):
        if self.action == "public_create":
            return [AllowAny()]
        if self.action in ["assignment", "request_assignment"]:
            return [CanAssignLead()]
        return super().get_permissions()

    # =====================
    # CREATE / UPDATE
    # =====================

    def perform_create(self, serializer):
        lead = serializer.save(status=self._get_default_status())
        self._send_notifications(lead)

    def _get_default_status(self):
        try:
            return LeadStatus.objects.get(code=RDV_A_CONFIRMER)
        except LeadStatus.DoesNotExist:
            raise NotFound("Le statut RDV_A_CONFIRMER n'existe pas en base.")

    def _send_notifications(self, lead):
        if getattr(lead.status, "code", None) != RDV_A_CONFIRMER:
            return

        # ✅ Django-Q2 : appel direct (plus de .delay())
        if lead.email:
            send_appointment_confirmation_task(lead.id)

        if lead.phone:
            send_appointment_confirmation_sms_task(lead.id)

    def perform_update(self, serializer):
        before = self.get_object()
        after = serializer.save()

        status_changed = before.status_id != after.status_id
        appointment_changed = before.appointment_date != after.appointment_date
        dossier_changed = (
            getattr(before.statut_dossier, "id", None)
            != getattr(after.statut_dossier, "id", None)
        )

        if status_changed or appointment_changed:
            self._send_notifications(after)

        if dossier_changed and after.statut_dossier:
            # ✅ Django-Q2 : appel direct (plus de .delay())
            send_dossier_status_notification_task(after.id)

    # =====================
    # ROUTES PERSONNALISÉES
    # =====================

    @action(
        detail=False,
        methods=["post"],
        url_path="public-create",
        permission_classes=[AllowAny],
    )
    def public_create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        appt_dt = serializer.validated_data.get("appointment_date")
        if not appt_dt:
            raise ValidationError({"appointment_date": "Champ requis."})

        with transaction.atomic():
            quota, _ = SlotQuota.objects.get_or_create(
                start_at=appt_dt,
                defaults={"capacity": 1, "booked": 0},
            )

            updated = SlotQuota.objects.filter(
                pk=quota.pk, booked__lt=F("capacity")
            ).update(booked=F("booked") + 1)

            if updated == 0:
                return Response(
                    {"detail": "Créneau complet. Veuillez choisir un autre horaire."},
                    status=drf_status.HTTP_409_CONFLICT,
                )

            lead = serializer.save(status=self._get_default_status())

        self._send_notifications(lead)
        return Response(
            self.get_serializer(lead).data,
            status=drf_status.HTTP_201_CREATED,
        )

    # =====================
    # STATS / DASHBOARD
    # =====================

    @action(detail=False, methods=["get"], url_path="count-by-status")
    def count_by_status(self, request):
        statuses = [RDV_A_CONFIRMER, A_RAPPELER, RDV_CONFIRME, ABSENT]
        status_qs = LeadStatus.objects.filter(code__in=statuses)
        status_map = {s.code: s for s in status_qs}

        data = {}
        for code in statuses:
            status_obj = status_map.get(code)
            data[code] = Lead.objects.filter(status=status_obj).count() if status_obj else 0

        return Response(data)

    @action(detail=False, methods=["get"], url_path="rdv-by-date")
    def rdv_by_date(self, request):
        date_str = request.query_params.get("date")
        if not date_str:
            return Response({"detail": "Le paramètre 'date' est requis (YYYY-MM-DD)."}, status=400)

        parsed_date = parse_date(date_str)
        if not parsed_date:
            return Response({"detail": "Format de date invalide."}, status=400)

        status = LeadStatus.objects.filter(code=RDV_CONFIRME).first()
        if not status:
            return Response({"detail": "Le statut RDV_CONFIRME n'existe pas."}, status=500)

        leads = (
            Lead.objects.filter(status=status, appointment_date__date=parsed_date)
            .order_by("appointment_date")
            .distinct()
        )

        return Response(self.get_serializer(leads, many=True).data)

    # =====================
    # ASSIGNATIONS
    # =====================

    @action(detail=True, methods=["patch"], url_path="assignment")
    def assignment(self, request, pk=None):
        lead = self.get_object()
        user = request.user
        action_type = request.data.get("action")
        assign_ids = request.data.get("assign", [])
        unassign_ids = request.data.get("unassign", [])

        if user.role not in [UserRoles.ADMIN, UserRoles.CONSEILLER, UserRoles.JURISTE]:
            raise PermissionDenied("Accès interdit.")

        if action_type == "assign":
            lead.assigned_to.add(user)
        elif action_type == "unassign":
            lead.assigned_to.remove(user)
        elif user.role == UserRoles.ADMIN:
            if assign_ids:
                lead.assigned_to.add(*User.objects.filter(id__in=assign_ids, is_active=True))
            if unassign_ids:
                lead.assigned_to.remove(*User.objects.filter(id__in=unassign_ids))
        else:
            return Response({"detail": "Action non autorisée."}, status=403)

        lead.save()
        return Response(self.get_serializer(lead).data)

    @action(detail=True, methods=["patch"], url_path="assign-juristes")
    def assign_juristes(self, request, pk=None):
        user = request.user
        if user.role != UserRoles.ADMIN:
            raise PermissionDenied("Admin requis.")

        lead = self.get_object()
        assign_ids = request.data.get("assign", [])
        unassign_ids = request.data.get("unassign", [])

        if assign_ids:
            users = User.objects.filter(
                id__in=assign_ids,
                role__in=[UserRoles.JURISTE, UserRoles.AVOCAT],
                is_active=True,
            )
            lead.jurist_assigned.add(*users)

            if lead.email and users.exists():
                # ✅ Django-Q2 : appel direct (plus de .delay())
                send_jurist_assigned_notification_task(lead.id, users.first().id)

        if unassign_ids:
            lead.jurist_assigned.remove(*User.objects.filter(id__in=unassign_ids))

        lead.save()
        return Response(self.get_serializer(lead).data)

    @action(detail=True, methods=["post"], url_path="send-formulaire-email")
    def send_formulaire_email(self, request, pk=None):
        lead = self.get_object()
        # ✅ Django-Q2 : appel direct (plus de .delay())
        send_formulaire_task(lead.id)
        return Response({"detail": "E-mail envoyé."}, status=200)