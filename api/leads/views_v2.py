from rest_framework import viewsets, permissions
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.decorators import action
from django.utils import timezone
from django.db.models import Case, When, F, DateTimeField, IntegerField, Q
from rest_framework import status

from api.core.pagination import CRMLeadPagination
from api.leads.models import Lead
from api.leads.serializers import LeadSerializer
from api.leads_events.models import LeadEvent
from api.users.roles import UserRoles
from api.users.models import User

from api.utils.email.leads.tasks import send_avocat_assigned_notification_task
from api.sms.tasks import send_avocat_assigned_sms_task


class LeadViewSetV2(viewsets.ModelViewSet):
    serializer_class = LeadSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = CRMLeadPagination

    # ==========================
    # QUERYSET
    # ==========================

    def get_queryset(self):
        user = self.request.user

        queryset = Lead.objects.all().prefetch_related(
            "assigned_to",        # ✅ Typo corrigée
            "jurist_assigned",
        )

        # ==========================
        # 🔒 FILTRAGE PAR RÔLE
        # ADMIN et JURISTE → accès total, aucun filtre
        # AVOCAT → uniquement ses leads assignés
        # ==========================
        if user.is_authenticated:
            if user.role == UserRoles.AVOCAT:
                queryset = queryset.filter(assigned_to=user)
            # ✅ JURISTE : plus de filtre restrictif → accès à tous les leads

        # ==========================
        # 🔍 FILTRES
        # ==========================
        queryset = self._filter_by_search(queryset)
        queryset = self._filter_by_status(queryset)
        queryset = self._filter_by_date(queryset)

        # ==========================
        # 🧠 TRI INTELLIGENT
        # ==========================

        # 👨‍⚖️ JURISTE → ses leads assignés remontent en premier, puis urgents, puis récents
        if user.role == UserRoles.JURISTE:
            queryset = queryset.annotate(
                assigned_order=Case(
                    When(assigned_to=user, then=0),
                    default=1,
                    output_field=IntegerField(),
                ),
                urgent_order=Case(
                    When(is_urgent=True, then=0),
                    default=1,
                    output_field=IntegerField(),
                ),
                has_appointment=Case(
                    When(appointment_date__isnull=False, then=0),
                    default=1,
                    output_field=IntegerField(),
                ),
                appointment_sort=Case(
                    When(appointment_date__isnull=False, then=F("appointment_date")),
                    default=F("created_at"),
                    output_field=DateTimeField(),
                )
            ).order_by(
                "assigned_order",  # 🔝 ses leads en premier
                "urgent_order",    # 🔥 urgents ensuite
                "-created_at",     # 🆕 récents
                "has_appointment",
                "appointment_sort",
            )

        # 👑 AUTRES → tri standard
        else:
            queryset = queryset.annotate(
                has_appointment=Case(
                    When(appointment_date__isnull=False, then=0),
                    default=1,
                    output_field=IntegerField(),
                ),
                appointment_sort=Case(
                    When(appointment_date__isnull=False, then=F("appointment_date")),
                    default=F("created_at"),
                    output_field=DateTimeField(),
                )
            ).order_by(
                "-created_at",
                "has_appointment",
                "appointment_sort",
            )

        return queryset

    # ==========================
    # SÉCURITÉ (DETAIL)
    # ✅ JURISTE : accès total, aucune restriction
    # AVOCAT : uniquement ses leads assignés
    # ==========================

    def get_object(self):
        from django.shortcuts import get_object_or_404
        obj = get_object_or_404(Lead, pk=self.kwargs["pk"])

        user = self.request.user

        if user.role == UserRoles.AVOCAT:
            if not obj.assigned_to.filter(id=user.id).exists():
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("Accès interdit à ce lead.")

        self.check_object_permissions(self.request, obj)
        return obj

    # ==========================
    # FILTRES
    # ==========================

    @action(
        detail=False,
        methods=["post"],
        url_path="public-create",
        permission_classes=[AllowAny]
    )
    def public_create(self, request):
        """
        Endpoint public pour créer un lead depuis le formulaire de booking.
        Sans authentification requise.
        """
        serializer = self.get_serializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {"error": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        lead = serializer.save()

        from api.clients.models import Client
        Client.objects.get_or_create(lead=lead)

        return Response(
            self.get_serializer(lead).data,
            status=status.HTTP_201_CREATED
        )

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
        if date_str:
            return queryset.filter(appointment_date__date=date_str)
        return queryset

    # ==========================
    # ASSIGN (1 lead)
    # ==========================

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        lead = self.get_object()
        user_ids = request.data.get("user_ids", [])

        if not isinstance(user_ids, list):
            return Response({"detail": "user_ids doit être une liste"}, status=400)

        lead.assigned_to.set(user_ids)

        users_to_assign = User.objects.filter(id__in=user_ids, role=UserRoles.AVOCAT)
        for avocat in users_to_assign:
            send_avocat_assigned_sms_task(lead.id, avocat.id)
            send_avocat_assigned_notification_task(lead.id, avocat.id)

        return Response({"success": True})

    # ==========================
    # ASSIGN JURISTS
    # ==========================

    @action(detail=True, methods=["post"])
    def assign_jurists(self, request, pk=None):
        lead = self.get_object()
        user_ids = request.data.get("user_ids", [])

        if not isinstance(user_ids, list):
            return Response({"detail": "user_ids doit être une liste"}, status=400)

        lead.jurist_assigned.set(user_ids)
        lead.juriste_assigned_at = timezone.now()
        lead.save(update_fields=["juriste_assigned_at"])

        return Response({"success": True})

    # ==========================
    # BULK ASSIGN
    # ==========================

    @action(detail=False, methods=["post"], url_path="bulk-assign")
    def bulk_assign(self, request):
        lead_ids = request.data.get("lead_ids", [])
        user_ids = request.data.get("user_ids", [])

        if not isinstance(lead_ids, list) or not isinstance(user_ids, list):
            return Response({"detail": "lead_ids et user_ids doivent être des listes"}, status=400)

        leads = self.get_queryset().filter(id__in=lead_ids)
        users_to_assign = list(User.objects.filter(id__in=user_ids, role=UserRoles.AVOCAT))

        for lead in leads:
            lead.assigned_to.set(user_ids)
            for avocat in users_to_assign:
                send_avocat_assigned_sms_task(lead.id, avocat.id)
                send_avocat_assigned_notification_task(lead.id, avocat.id)

        return Response({"success": True, "updated": leads.count()})

    # ==========================
    # BULK ASSIGN JURISTS
    # ==========================

    @action(detail=False, methods=["post"], url_path="bulk-assign-jurists")
    def bulk_assign_jurists(self, request):
        lead_ids = request.data.get("lead_ids", [])
        user_ids = request.data.get("user_ids", [])

        if not isinstance(lead_ids, list) or not isinstance(user_ids, list):
            return Response({"detail": "lead_ids et user_ids doivent être des listes"}, status=400)

        leads = self.get_queryset().filter(id__in=lead_ids)

        for lead in leads:
            lead.jurist_assigned.set(user_ids)
            lead.juriste_assigned_at = timezone.now()
            lead.save(update_fields=["juriste_assigned_at"])

        return Response({"success": True, "updated": leads.count()})

    # ==========================
    # CREATE
    # ==========================

    def perform_create(self, serializer):
        lead = serializer.save()

        from api.clients.models import Client
        Client.objects.get_or_create(lead=lead)

    # ==========================
    # UPDATE
    # ==========================

    def perform_update(self, serializer):
        serializer.save()