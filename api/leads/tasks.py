import logging
from datetime import timedelta
from itertools import cycle

from django.utils import timezone
from django.db import transaction
from django_q.tasks import async_task  # ✅ Import crucial pour Django-Q2

from api.leads.models import Lead
from api.lead_status.models import LeadStatus
from api.leads_task.models import LeadTask
from api.leads_task_type.models import LeadTaskType
from api.users.models import User
from api.users.roles import UserRoles
from api.leads_task.constants import LeadTaskStatus, LeadTaskPriority  # ✅ Ajout de LeadTaskPriority
from api.leads.constants import (
    PRESENT,
    ABSENT,
    ANNULE,
    RDV_CONFIRME,
    RDV_PLANIFIE,
)

# Notifications imports
from api.sms.tasks import (
    send_absent_urgency_sms_task,
    send_appointment_reminder_48h_sms_task,
    send_appointment_reminder_24h_sms_task,
)
from api.utils.email.leads.tasks import (
    send_appointment_absent_email_task,
    send_appointment_reminder_email_task,
)

logger = logging.getLogger(__name__)


# =========================================================
# 1. GESTION DES ABSENCES (DÉTECTION + NOTIFICATION)
# =========================================================

def mark_missed_appointments_as_absent():
    """
    Détecte intelligemment TOUS les RDV passés non honorés.
    """
    now = timezone.now()

    try:
        absent_status = LeadStatus.objects.get(code=ABSENT)
    except LeadStatus.DoesNotExist:
        logger.error("❌ Status ABSENT non trouvé dans la base")
        return "0 leads updated - Status ABSENT missing"

    # On cible ce qui est dans le passé et non traité
    leads_qs = Lead.objects.filter(
        appointment_date__isnull=False,
        appointment_date__lt=now,
    ).exclude(
        status__code__in=[PRESENT, ABSENT, ANNULE]
    )

    lead_ids = list(leads_qs.values_list("id", flat=True))

    if not lead_ids:
        logger.info("✅ Aucun nouveau rendez-vous manqué détecté.")
        return "0 leads marked as absent"

    try:
        with transaction.atomic():
            updated_count = leads_qs.update(status=absent_status)

        # 🚀 Dispatch des notifications via Django-Q2
        for lead_id in lead_ids:
            async_task(send_absent_urgency_sms_task, lead_id)
            async_task(send_appointment_absent_email_task, lead_id)
            logger.info(f"📢 Notifications d'absence mises en file pour le lead #{lead_id}")

        return f"{updated_count} leads passés en ABSENT."

    except Exception as e:
        logger.error(f"❌ Erreur lors de la mise à jour massive : {str(e)}")
        return f"Error: {str(e)}"


# =========================================================
# 2. CRÉATION DES TÂCHES CRM (POUR L'ACCUEIL)
# =========================================================

def create_absent_followup_tasks(limit_per_user_per_day=20):
    """
    Crée des tâches de relance internes pour l'équipe ACCUEIL.
    """
    now = timezone.now()

    task_type, _ = LeadTaskType.objects.get_or_create(
        code="RELANCE_ABSENT",
        defaults={
            "label": "Relance client absent",
            "description": "Appeler le client pour reprogrammer un rendez-vous.",
        },
    )

    accueil_users = list(User.objects.filter(role=UserRoles.ACCUEIL, is_active=True))
    if not accueil_users:
        logger.warning("⚠️ Aucun agent d'accueil actif.")
        return "Abort: No active ACCUEIL users"

    active_tasks_leads = LeadTask.objects.filter(
        task_type=task_type,
        status=LeadTaskStatus.TODO
    ).values_list('lead_id', flat=True)

    leads_to_process = Lead.objects.filter(
        status__code=ABSENT,
        appointment_date__isnull=False,
    ).exclude(id__in=active_tasks_leads).order_by('-appointment_date')

    if not leads_to_process.exists():
        return "No new tasks to create"

    num_agents = len(accueil_users)
    user_pool = cycle(accueil_users)
    daily_capacity = num_agents * limit_per_user_per_day

    created_count = 0

    with transaction.atomic():
        for index, lead in enumerate(leads_to_process):
            days_offset = index // daily_capacity
            scheduled_date = now + timedelta(days=days_offset)
            agent = next(user_pool)

            LeadTask.objects.create(
                lead=lead,
                task_type=task_type,
                title=f"Relancer {lead.first_name} {lead.last_name}",
                description=f"Rendez-vous manqué le {lead.appointment_date.strftime('%d/%m/%Y')}.",
                due_at=scheduled_date,
                assigned_to=agent,
                status=LeadTaskStatus.TODO,
                priority=LeadTaskPriority.MEDIUM,  # ✅ Fix : champ priority explicitement renseigné
            )
            created_count += 1

    return f"{created_count} internal tasks created."


# =========================================================
# 3. RAPPELS DE RENDEZ-VOUS (AVANT LE RDV)
# =========================================================

def send_appointment_reminders():
    """
    Envoie des rappels automatiques (SMS+EMAIL) 48h et 24h avant le rendez-vous.
    """
    now = timezone.now()
    tolerance = timedelta(minutes=10)  # Fenêtre de tir

    reminder_windows = [
        (timedelta(hours=48), "48h", send_appointment_reminder_48h_sms_task),
        (timedelta(hours=24), "24h", send_appointment_reminder_24h_sms_task),
    ]

    total_sent = 0

    for delta, label, sms_task_func in reminder_windows:
        target_time = now + delta

        leads = Lead.objects.filter(
            appointment_date__gte=target_time - tolerance,
            appointment_date__lte=target_time + tolerance,
            status__code__in=[RDV_CONFIRME, RDV_PLANIFIE],
        )

        for lead in leads:
            # Sécurité anti-doublon (20h)
            if lead.last_reminder_sent and (now - lead.last_reminder_sent) < timedelta(hours=20):
                continue

            async_task(sms_task_func, lead.id)
            async_task(send_appointment_reminder_email_task, lead.id)

            # Mise à jour du timestamp pour éviter les doublons au prochain cycle
            lead.last_reminder_sent = now
            lead.save(update_fields=["last_reminder_sent"])

            total_sent += 1
            logger.info(f"✅ Rappel {label} mis en file pour le lead #{lead.id}")

    return f"{total_sent} reminders sent"