# api/leads_task/tasks.py

import logging
import random

from celery import shared_task
from django.utils import timezone

from api.leads.models import Lead
from api.leads_task.models import LeadTask
from api.leads_task_type.models import LeadTaskType
from api.leads_task_status.models import LeadTaskStatus
from api.leads_events.models import LeadEvent

from api.users.models import User
from api.users.roles import UserRoles

logger = logging.getLogger(__name__)


@shared_task
def create_absent_followup_task(lead_id: int, triggered_event_id: int = None):
    """
    Crée automatiquement une tâche de relance lorsqu’un lead devient ABSENT.

    ✔ due_at = instant du passage ABSENT
    ✔ assignation automatique à un utilisateur ACCUEIL actif
    ✔ anti-doublon robuste
    ✔ traçabilité via LeadEvent
    """

    # --------------------------------------------------
    # Récupération du lead
    # --------------------------------------------------

    lead = Lead.objects.filter(id=lead_id).select_related("status").first()

    if not lead:
        logger.warning(
            "[create_absent_followup_task] Lead #%s introuvable — ignoré",
            lead_id,
        )
        return

    # --------------------------------------------------
    # Anti-doublon (task déjà existante ?)
    # --------------------------------------------------

    already_exists = LeadTask.objects.filter(
        lead=lead,
        task_type__code="RELANCE_LEAD",
        completed_at__isnull=True,
    ).exists()

    if already_exists:
        logger.info(
            "[create_absent_followup_task] Tâche déjà existante — ignoré : lead_id=%s",
            lead_id,
        )
        return

    # --------------------------------------------------
    # Anti-doublon via event (sécurité supplémentaire)
    # --------------------------------------------------

    already_created = LeadEvent.objects.filter(
        lead=lead,
        event_type__code="TASK_RELANCE_CREATED"
    ).exists()

    if already_created:
        return

    # --------------------------------------------------
    # Récupération type + statut
    # --------------------------------------------------

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

    # --------------------------------------------------
    # Récupération event déclencheur
    # --------------------------------------------------

    triggered_by_event = None

    if triggered_event_id:
        triggered_by_event = LeadEvent.objects.filter(
            id=triggered_event_id
        ).first()

    # --------------------------------------------------
    # Attribution automatique (ACCUEIL actifs)
    # --------------------------------------------------

    accueil_users = User.objects.filter(
        role=UserRoles.ACCUEIL,
        is_active=True
    )

    assigned_user = None

    if accueil_users.exists():
        assigned_user = random.choice(list(accueil_users))

    # --------------------------------------------------
    # Échéance = MAINTENANT (🔥 ton besoin)
    # --------------------------------------------------

    due_at = timezone.now()

    # --------------------------------------------------
    # Création de la tâche
    # --------------------------------------------------

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

    # --------------------------------------------------
    # Log de traçabilité
    # --------------------------------------------------

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
        task.id,
        lead.id,
        assigned_user.id if assigned_user else None
    )