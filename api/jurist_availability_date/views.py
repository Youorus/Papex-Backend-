# ==========================================
# BACKEND DJANGO - views.py
# api/jurist_availability_date/views.py
# ==========================================

from rest_framework import permissions, viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from datetime import date, datetime
from django.contrib.auth import get_user_model
from django.utils.dateparse import parse_date

from api.jurist_appointment.serializers import JuristSerializer
from api.jurist_availability_date.models import JuristGlobalAvailability
from api.jurist_availability_date.serializers import (
    JuristGlobalAvailabilitySerializer,
    AvailabilityStatsSerializer,
)
from api.user_unavailability.models import UserUnavailability
from api.utils.jurist_slots import get_available_slots_for_jurist

User = get_user_model()


class JuristGlobalAvailabilityViewSet(viewsets.ModelViewSet):
    queryset = JuristGlobalAvailability.objects.all()
    serializer_class = JuristGlobalAvailabilitySerializer

    def get_permissions(self):
        """Lecture pour tous, écriture pour admin/staff"""
        if self.action in ["list", "retrieve", "days", "available_jurists", "stats"]:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def get_queryset(self):
        """Filtre les disponibilités selon les paramètres"""
        queryset = super().get_queryset()

        # Filtre par type
        availability_type = self.request.query_params.get('type', None)
        if availability_type in ['global', 'specific']:
            queryset = queryset.filter(availability_type=availability_type)

        # Filtre par juriste
        jurist_id = self.request.query_params.get('jurist_id', None)
        if jurist_id:
            queryset = queryset.filter(jurist_id=jurist_id)

        # Filtre par date
        date_from = self.request.query_params.get('date_from', None)
        date_to = self.request.query_params.get('date_to', None)

        if date_from:
            queryset = queryset.filter(date__gte=date_from)
        if date_to:
            queryset = queryset.filter(date__lte=date_to)

        return queryset.select_related('jurist').order_by('date', 'start_time')

    def get_serializer_context(self):
        """Ajoute des options au contexte du serializer"""
        context = super().get_serializer_context()
        context['include_slots'] = self.request.query_params.get('include_slots', 'false').lower() == 'true'
        return context

    @action(detail=False, methods=["get"], permission_classes=[permissions.AllowAny])
    def days(self, request):
        """Retourne la liste des jours avec disponibilités"""
        include_weekly = request.query_params.get('include_weekly', 'true').lower() == 'true'

        days = set()

        # Récupère TOUTES les disponibilités actives
        qs = JuristGlobalAvailability.objects.filter(is_active=True)

        for avail in qs:
            # ✅ TOUJOURS ajouter la date exacte
            days.add(avail.date.isoformat())

            # ✅ Si répétition hebdomadaire activée, ajouter aussi le jour de la semaine
            if avail.repeat_weekly and include_weekly:
                days.add(f"weekly-{avail.date.weekday()}")

        return Response({
            'days': sorted(days),
            'count': len(days)
        })

    @action(detail=False, methods=["get"], permission_classes=[permissions.AllowAny])
    def available_jurists(self, request):
        """
        Retourne la liste des juristes disponibles pour une date donnée.
        """
        date_str = request.query_params.get("date")
        if not date_str:
            return Response(
                {"detail": "Le paramètre 'date' est requis."},
                status=status.HTTP_400_BAD_REQUEST
            )

        day = parse_date(date_str)
        if not day:
            return Response(
                {"detail": "Format de date invalide. Utilisez YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 1. Récupérer les IDs des juristes indisponibles ce jour-là
        unavailable_ids = set(
            UserUnavailability.objects.filter(
                start_date__lte=day,
                end_date__gte=day
            ).values_list("user_id", flat=True)
        )

        # 2. Récupérer tous les juristes actifs (non indisponibles)
        all_jurists = User.objects.filter(
            role="JURISTE",
            is_active=True
        ).exclude(id__in=unavailable_ids)

        # 3. Filtrer ceux qui ont des créneaux disponibles
        available_jurists = []
        for jurist in all_jurists:
            slots = get_available_slots_for_jurist(jurist, day)
            if slots:
                available_jurists.append(jurist)

        # 4. Sérialiser et retourner
        serializer = JuristSerializer(available_jurists, many=True)

        return Response({
            "jurists": serializer.data,
            "count": len(available_jurists)
        })

    @action(detail=False, methods=["get"], permission_classes=[permissions.AllowAny])
    def stats(self, request):
        """Retourne des statistiques sur les disponibilités"""
        qs = self.get_queryset()

        stats = {
            'total_availabilities': qs.count(),
            'global_availabilities': qs.filter(availability_type='global').count(),
            'specific_availabilities': qs.filter(availability_type='specific').count(),
            'total_slots': sum(avail.available_slots_count for avail in qs),
            'active_jurists': qs.filter(availability_type='specific').values('jurist').distinct().count(),
        }

        serializer = AvailabilityStatsSerializer(stats)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAdminUser])
    def toggle_active(self, request, pk=None):
        """Active/désactive une disponibilité sans la supprimer"""
        availability = self.get_object()
        availability.is_active = not availability.is_active
        availability.save()

        serializer = self.get_serializer(availability)
        return Response(serializer.data)

    @action(detail=False, methods=["post"], permission_classes=[permissions.IsAdminUser])
    def bulk_create(self, request):
        """
        Crée plusieurs disponibilités en une seule requête.
        """
        availabilities_data = request.data.get('availabilities', [])

        if not availabilities_data:
            return Response(
                {'error': 'Le champ "availabilities" est requis'},
                status=status.HTTP_400_BAD_REQUEST
            )

        created = []
        errors = []

        for idx, data in enumerate(availabilities_data):
            serializer = self.get_serializer(data=data)
            if serializer.is_valid():
                serializer.save()
                created.append(serializer.data)
            else:
                errors.append({
                    'index': idx,
                    'data': data,
                    'errors': serializer.errors
                })

        return Response({
            'created': created,
            'created_count': len(created),
            'errors': errors,
            'errors_count': len(errors)
        }, status=status.HTTP_201_CREATED if created else status.HTTP_400_BAD_REQUEST)