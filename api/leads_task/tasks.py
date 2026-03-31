# api/leads_task/tasks.py
# ✅ Migré Celery → Django-Q2

import logging
import random

from django_q.tasks import async_task
from django.utils import timezone

from api.leads.models import Lead
from api.leads_task.models import LeadTask
from api.leads_task_type.models import LeadTaskType
from api.leads_task_status.models import LeadTaskStatus
from api.leads_events.models import LeadEvent
from api.users.models import User
from api.users.roles import UserRoles

logger = logging.getLogger(__name__)


# ================================================================
# WORKER
# ================================================================

def _run_create_absent_followup_task(lead_id: int, triggered_event_id: int = None):
    lead = Lead.objects.filter(id=lead_id).select_related("status").first()

    if not lead:
        logger.warning("[create_absent_followup_task] Lead #%s introuvable — ignoré", lead_id)
        return

    # Anti-doublon tâche
    already_exists = LeadTask.objects.filter(
        lead=lead,
        task_type__code="RELANCE_LEAD",
        completed_at__isnull=True,
    ).exists()

    if already_exists:
        logger.info("[create_absent_followup_task] Tâche déjà existante — ignoré : lead_id=%s", lead_id)
        return

    # Anti-doublon event
    already_created = LeadEvent.objects.filter(
        lead=lead,
        event_type__code="TASK_RELANCE_CREATED"
    ).exists()

    if already_created:
        return

    # Récupération type + statut
    try:
        task_type = LeadTaskType.objects.get(code="RELANCE_LEAD")
    except LeadTaskType.DoesNotExist:
        logger.error("LeadTaskType RELANCE_LEAD introuvable")
        return

    try:
        task_status = LeadTaskStatus.objects.get(code="A_FAIRE")
    except LeadTaskStatus.DoesNotExist:
        logger.error("LeadTaskStatus A_FAIRE introuvable")
        return

    # Event déclencheur
    triggered_by_event = None
    if triggered_event_id:
        triggered_by_event = LeadEvent.objects.filter(id=triggered_event_id).first()

    # Attribution ACCUEIL
    accueil_users = User.objects.filter(role=UserRoles.ACCUEIL, is_active=True)
    assigned_user = random.choice(list(accueil_users)) if accueil_users.exists() else None

    due_at = timezone.now()

    task = LeadTask.objects.create(
        lead=lead,
        task_type=task_type,
        status=task_status,
        title=(
            f"Relance — absent au RDV du "
            f"{lead.appointment_date.strftime('%d/%m/%Y à %Hh%M') if lead.appointment_date else 'RDV'}"
        ),
        description=(
            "Le lead n'était pas présent à son rendez-vous.\n"
            "À rappeler immédiatement pour reprogrammer."
        ),
        due_at=due_at,
        assigned_to=assigned_user,
        triggered_by_event=triggered_by_event,
        metadata={
            "auto_created": True,
            "trigger": "ABSENT",
            "appointment_date": lead.appointment_date.isoformat() if lead.appointment_date else None,
        },
    )

    LeadEvent.log(
        lead=lead,
        event_code="TASK_RELANCE_CREATED",
        data={
            "task_id": task.id,
            "assigned_to": str(assigned_user.id) if assigned_user else None,
        }
    )

    logger.info(
        "[create_absent_followup_task] Task créée : task_id=%s | lead_id=%s | assigned_to=%s",
        task.id, lead.id, assigned_user.id if assigned_user else None
    )


# ================================================================
# API PUBLIQUE — dispatch
# ================================================================

def create_absent_followup_task(lead_id: int, triggered_event_id: int = None):
    """Dispatch la création de tâche relance absent. Anciennement .delay()"""
    async_task(
        "api.leads_task.tasks._run_create_absent_followup_task",
        lead_id,
        triggered_event_id,
        group="crm",
    )