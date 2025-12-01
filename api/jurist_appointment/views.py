from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.http import HttpResponse

from api.leads.models import Lead
from api.jurist_availability_date.models import JuristGlobalAvailability
from ..user_unavailability.models import UserUnavailability
from ..users.roles import UserRoles
from ..utils.email.jurist_appointment.tasks import (
    send_jurist_appointment_created_task,
    send_jurist_appointment_deleted_task,
)
from ..utils.jurist_slots import get_available_slots_for_jurist, is_valid_day
from .models import JuristAppointment
from .serializers import (
    JuristAppointmentCreateSerializer,
    JuristAppointmentSerializer,
    JuristSerializer,
)

# Import pour la génération PDF
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from io import BytesIO
from datetime import datetime, timedelta
from collections import defaultdict
import pytz  # ✅ NOUVEAU IMPORT pour le fuseau horaire
import logging
logger = logging.getLogger(__name__)
User = get_user_model()


def convert_to_django_weekday(python_date):
    django_weekday = (python_date.weekday() + 2) % 7
    return 7 if django_weekday == 0 else django_weekday


class JuristAppointmentViewSet(viewsets.ModelViewSet):
    queryset = JuristAppointment.objects.all().select_related("jurist", "lead")
    serializer_class = JuristAppointmentSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["lead__id", "date"]

    def perform_create(self, serializer):
        instance = serializer.save()
        send_jurist_appointment_created_task.delay(instance.id)

    def perform_destroy(self, instance):
        lead = instance.lead
        jurist = instance.jurist
        appointment_date = instance.date
        instance.delete()
        send_jurist_appointment_deleted_task.delay(
            lead.id, jurist.id, appointment_date.isoformat()
        )

    def get_queryset(self):
        qs = super().get_queryset()
        # --- Filtres additionnels ---
        lead = self.request.query_params.get("lead")
        date_str = self.request.query_params.get("date")  # attendu: YYYY-MM-DD

        if lead:
            qs = qs.filter(lead_id=lead)

        if date_str:
            day = parse_date(date_str)
            if day:
                qs = qs.filter(date__date=day)

        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return JuristAppointmentCreateSerializer
        return JuristAppointmentSerializer

    @action(detail=False, methods=["get"])
    def available_jurists(self, request):
        """
        ✅ VERSION CORRIGÉE
        Retourne la liste des juristes dispos pour une date donnée,
        en tenant compte des disponibilités globales ET spécifiques.
        """
        date_str = request.query_params.get("date")
        if not date_str:
            return Response({"detail": "date requis."}, status=400)

        day = parse_date(date_str)
        if not day:
            return Response({"detail": "Date invalide."}, status=400)

        # ✅ CORRECTION : Utiliser la bonne conversion de jour
        django_weekday = convert_to_django_weekday(day)

        # 1. Vérifier s'il y a des disponibilités (globales ou spécifiques) pour ce jour
        has_global_availability = JuristGlobalAvailability.objects.filter(
            Q(date=day) | Q(repeat_weekly=True, date__week_day=django_weekday),
            availability_type='global',
            is_active=True
        ).exists()

        has_specific_availability = JuristGlobalAvailability.objects.filter(
            Q(date=day) | Q(repeat_weekly=True, date__week_day=django_weekday),
            availability_type='specific',
            is_active=True
        ).exists()

        # Si aucune disponibilité ni globale ni spécifique, retourner liste vide
        if not has_global_availability and not has_specific_availability:
            return Response({
                "jurists": [],
                "count": 0
            })

        # 2. Liste des IDs de juristes indisponibles ce jour-là
        unavailable_ids = set(
            UserUnavailability.objects.filter(
                start_date__lte=day, end_date__gte=day
            ).values_list("user_id", flat=True)
        )

        # 3. Récupérer les juristes selon le type de disponibilité
        if has_global_availability:
            # Si disponibilité globale : TOUS les juristes actifs (sauf indisponibles)
            jurists_query = User.objects.filter(
                role="JURISTE",
                is_active=True
            ).exclude(id__in=unavailable_ids)
        else:
            # Sinon, seulement les juristes avec disponibilités spécifiques
            jurists_with_specific = User.objects.filter(
                role="JURISTE",
                is_active=True,
                specific_availabilities__in=JuristGlobalAvailability.objects.filter(
                    Q(date=day) | Q(repeat_weekly=True, date__week_day=django_weekday),
                    availability_type='specific',
                    is_active=True
                )
            ).distinct()
            jurists_query = jurists_with_specific.exclude(id__in=unavailable_ids)

        # 4. Filtrer ceux qui ont des créneaux disponibles
        available_jurists = [j for j in jurists_query if get_available_slots_for_jurist(j, day)]

        serializer = JuristSerializer(available_jurists, many=True)

        return Response({
            "jurists": serializer.data,
            "count": len(available_jurists)
        })

    @action(detail=False, methods=["get"])
    def jurist_slots(self, request):
        jurist_id = request.query_params.get("jurist_id")
        date_str = request.query_params.get("date")

        if not jurist_id or not date_str:
            return Response({"detail": "jurist_id et date requis."}, status=400)

        jurist = User.objects.filter(id=jurist_id, role="JURISTE", is_active=True).first()
        if not jurist:
            return Response({"detail": "Juriste introuvable."}, status=400)

        day = parse_date(date_str)
        if not day:
            return Response({"detail": "Date invalide."}, status=400)

        slots = get_available_slots_for_jurist(jurist, day)
        return Response(slots)

    @action(detail=False, methods=["get"])
    def upcoming_for_lead(self, request):
        lead_id = request.query_params.get("lead_id")
        if not lead_id:
            return Response({"detail": "lead_id requis."}, status=400)
        appointments = self.get_queryset().filter(lead_id=lead_id).order_by("date")
        serializer = self.get_serializer(appointments, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="available-days")
    def available_days(self, request):
        """
        ✅ VERSION CORRIGÉE
        Retourne les jours où il y a des disponibilités (globales ou spécifiques)
        """
        # Récupérer toutes les disponibilités actives
        availabilities = JuristGlobalAvailability.objects.filter(is_active=True)

        days = set()
        for avail in availabilities:
            if avail.repeat_weekly:
                # Pour les récurrences, ajouter le format "weekly-X"
                days.add(f"weekly-{avail.date.weekday()}")
            else:
                # Pour les dates exactes
                days.add(avail.date.isoformat())

        return Response({
            'days': sorted(days),
            'count': len(days)
        })

    @action(detail=False, methods=["get"], url_path="export-pdf")
    def export_appointments_pdf(self, request):
        """
        Exporte tous les rendez-vous des juristes au format PDF professionnel.

        Query params:
        - start_date (optionnel): Date de début (YYYY-MM-DD)
        - end_date (optionnel): Date de fin (YYYY-MM-DD)
        - jurist_id (optionnel): Filtrer par juriste spécifique

        Par défaut: 7 prochains jours
        """
        # ✅ Fuseau horaire de Paris
        paris_tz = pytz.timezone("Europe/Paris")

        # Récupération des paramètres
        start_date_str = request.query_params.get("start_date")
        end_date_str = request.query_params.get("end_date")
        jurist_param = request.query_params.get("jurist_id")

        logger.info(f"📥 Params reçus : start_date={start_date_str}, end_date={end_date_str}, jurist_id={jurist_param!r}")

        # Normalisation : jurist_id n'est valide que si vraiment fourni
        if jurist_param in (None, "", "null", "None"):
            jurist_id = None
        else:
            jurist_id = jurist_param

        logger.info(f"🔎 jurist_id normalisé : {jurist_id}")

        # 🔒 Si l'utilisateur connecté est un juriste → filtrage automatique
        user_role = getattr(request.user, "role", None)
        if user_role == "JURISTE":
            logger.info(f"🧑‍⚖️ Utilisateur connecté = juriste ({request.user.id})")

            if jurist_id is None:
                jurist_id = str(request.user.id)
                logger.info(f"➡️ Filtrage automatique sur le juriste connecté : {jurist_id}")
            else:
                logger.info(f"➡️ jurist_id fourni → override accepté : {jurist_id}")
        else:
            logger.info(f"👤 Utilisateur connecté rôle = {user_role}")

        # Dates de référence en timezone Paris
        now_paris = timezone.now().astimezone(paris_tz)
        today = now_paris.date()

        if start_date_str:
            start_date = parse_date(start_date_str) or today
        else:
            start_date = today

        if end_date_str:
            end_date = parse_date(end_date_str) or (today + timedelta(days=7))
        else:
            end_date = today + timedelta(days=7)

        # Construction de la requête
        appointments = JuristAppointment.objects.select_related(
            "jurist", "lead"
        ).filter(
            date__date__gte=start_date,
            date__date__lte=end_date
        ).order_by("date", "jurist__last_name")

        # Filtre optionnel par juriste
        if jurist_id:
            appointments = appointments.filter(jurist_id=jurist_id)

        # Organisation des rendez-vous par jour
        appointments_by_day = defaultdict(lambda: defaultdict(list))
        for apt in appointments:
            # ✅ Conversion en timezone Paris pour l'affichage
            apt_date_paris = apt.date.astimezone(paris_tz)
            day_key = apt_date_paris.date()
            jurist_name = f"{apt.jurist.first_name} {apt.jurist.last_name}"
            appointments_by_day[day_key][jurist_name].append({
                'time': apt_date_paris,
                'lead': apt.lead
            })

        # Génération du PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm
        )

        # Styles
        styles = getSampleStyleSheet()

        # ✅ Style titre principal en français
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#1a365d'),
            spaceAfter=20,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )

        # ✅ Style titre de jour en français
        day_title_style = ParagraphStyle(
            'DayTitle',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#2d3748'),
            spaceAfter=10,
            spaceBefore=15,
            fontName='Helvetica-Bold'
        )

        # ✅ Style titre juriste en français
        jurist_title_style = ParagraphStyle(
            'JuristTitle',
            parent=styles['Heading3'],
            fontSize=12,
            textColor=colors.HexColor('#4a5568'),
            spaceAfter=8,
            spaceBefore=10,
            fontName='Helvetica-Bold'
        )

        # ✅ Dictionnaire des jours de la semaine en français
        FRENCH_DAYS = {
            'Monday': 'Lundi',
            'Tuesday': 'Mardi',
            'Wednesday': 'Mercredi',
            'Thursday': 'Jeudi',
            'Friday': 'Vendredi',
            'Saturday': 'Samedi',
            'Sunday': 'Dimanche'
        }

        # ✅ Dictionnaire des mois en français
        FRENCH_MONTHS = {
            'January': 'Janvier',
            'February': 'Février',
            'March': 'Mars',
            'April': 'Avril',
            'May': 'Mai',
            'June': 'Juin',
            'July': 'Juillet',
            'August': 'Août',
            'September': 'Septembre',
            'October': 'Octobre',
            'November': 'Novembre',
            'December': 'Décembre'
        }

        # Construction du contenu
        story = []

        # ✅ Titre principal en français
        title_text = f"Planning des Rendez-vous Juristes<br/>{start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}"
        story.append(Paragraph(title_text, title_style))
        story.append(Spacer(1, 0.5 * cm))

        # ✅ Info génération en français avec heure de Paris
        generation_time_paris = now_paris.strftime('%d/%m/%Y à %H:%M')
        generation_info = f"<i>Généré le {generation_time_paris} (heure de Paris)</i>"
        story.append(Paragraph(generation_info, styles['Normal']))
        story.append(Spacer(1, 1 * cm))

        # Compteurs
        total_appointments = 0
        total_days = len(appointments_by_day)

        # Parcours des jours
        for day in sorted(appointments_by_day.keys()):
            # ✅ Formatage de la date en français
            english_day_name = day.strftime('%A')
            english_month_name = day.strftime('%B')
            french_day_name = FRENCH_DAYS.get(english_day_name, english_day_name)
            french_month_name = FRENCH_MONTHS.get(english_month_name, english_month_name)

            day_formatted = day.strftime(f'{french_day_name} %d {french_month_name} %Y')
            day_title = f"📅 {day_formatted}"
            story.append(Paragraph(day_title, day_title_style))

            jurists_data = appointments_by_day[day]

            # Parcours des juristes pour ce jour
            for jurist_name in sorted(jurists_data.keys()):
                apts = jurists_data[jurist_name]
                total_appointments += len(apts)

                # ✅ Nom du juriste en français
                jurist_title = f"👤 {jurist_name} ({len(apts)} RDV)"
                story.append(Paragraph(jurist_title, jurist_title_style))

                # ✅ Tableau des rendez-vous avec en-têtes en français
                table_data = [
                    ["Heure", "Client", "Téléphone", "Email"]
                ]

                for apt_data in apts:
                    apt_time = apt_data['time']
                    lead = apt_data['lead']

                    # ✅ Heure en format français (Paris)
                    time_str = apt_time.strftime('%H:%M')

                    table_data.append([
                        time_str,
                        f"{lead.first_name} {lead.last_name}",
                        lead.phone or "-",
                        lead.email or "-"
                    ])

                # Création du tableau
                table = Table(table_data, colWidths=[3 * cm, 5 * cm, 4 * cm, 5 * cm])
                table.setStyle(TableStyle([
                    # En-tête
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4299e1')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),

                    # Corps du tableau
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                    ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # Heure centrée
                    ('ALIGN', (1, 1), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 9),
                    ('TOPPADDING', (0, 1), (-1, -1), 8),
                    ('BOTTOMPADDING', (0, 1), (-1, -1), 8),

                    # Bordures
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor('#2c5282')),

                    # Alternance de couleurs
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1),
                     [colors.white, colors.HexColor('#f7fafc')]),
                ]))

                story.append(table)
                story.append(Spacer(1, 0.5 * cm))

            # Séparateur entre les jours (sauf dernier)
            if day != max(appointments_by_day.keys()):
                story.append(Spacer(1, 0.3 * cm))
                story.append(Paragraph("<hr width='100%'/>", styles['Normal']))

        # ✅ Résumé final en français
        if total_appointments > 0:
            story.append(Spacer(1, 1 * cm))
            summary = f"<b>Résumé :</b> {total_appointments} rendez-vous sur {total_days} jour(s)"
            story.append(Paragraph(summary, styles['Normal']))
        else:
            story.append(Paragraph(
                "<i>Aucun rendez-vous trouvé pour la période sélectionnée.</i>",
                styles['Normal']
            ))

        # Construction du PDF
        doc.build(story)

        # Préparation de la réponse
        buffer.seek(0)
        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
        filename = f"planning_juristes_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        return response