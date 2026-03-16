# api/leads_task/tasks.py

import logging

from celery import shared_task
from django.utils import timezone
from datetime import timedelta

from api.leads.models import Lead
from api.leads_task.models import LeadTask
from api.leads_task_type.models import LeadTaskType
from api.leads_task_status.models import LeadTaskStatus
from api.leads_events.models import LeadEvent

logger = logging.getLogger(__name__)

# Délai avant échéance de la tâche de relance après absence (en heures)
RELANCE_DELAY_HOURS = 2


# ============================================================
# ⚙️ CRÉATION TÂCHE DE RELANCE — LEAD ABSENT
# ============================================================

@shared_task
def create_absent_followup_task(lead_id: int, triggered_event_id: int = None):
    """
    Crée une tâche de relance commerciale (RELANCE_LEAD)
    suite à l'absence du lead à son RDV.

    Échéance : +2h après le marquage absent, pour que le
    commercial puisse rappeler dans la journée.

    Si une tâche RELANCE_LEAD est déjà ouverte pour ce lead,
    on ne crée pas de doublon.

    triggered_event_id : ID du LeadEvent STATUS_CHANGED → ABSENT
    qui a déclenché cette task (pour traçabilité via triggered_by_event).
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
    # Anti-doublon : tâche RELANCE_LEAD déjà ouverte ?
    # --------------------------------------------------

    already_exists = LeadTask.objects.filter(
        lead=lead,
        task_type__code="RELANCE_LEAD",
        completed_at__isnull=True,
    ).exists()

    if already_exists:
        logger.info(
            "[create_absent_followup_task] Tâche RELANCE_LEAD déjà ouverte — ignoré : lead_id=%s",
            lead_id,
        )
        return

    # --------------------------------------------------
    # Récupération du type et statut de tâche
    # --------------------------------------------------

    try:
        task_type = LeadTaskType.objects.get(code="RELANCE_LEAD")
    except LeadTaskType.DoesNotExist:
        logger.error(
            "[create_absent_followup_task] LeadTaskType RELANCE_LEAD introuvable en base"
        )
        return

    try:
        task_status = LeadTaskStatus.objects.get(code="A_FAIRE")
    except LeadTaskStatus.DoesNotExist:
        logger.error(
            "[create_absent_followup_task] LeadTaskStatus A_FAIRE introuvable en base"
        )
        return

    # --------------------------------------------------
    # Récupération de l'événement déclencheur (optionnel)
    # --------------------------------------------------

    triggered_by_event = None

    if triggered_event_id:
        triggered_by_event = LeadEvent.objects.filter(
            id=triggered_event_id
        ).first()

    # --------------------------------------------------
    # Calcul de l'échéance
    # --------------------------------------------------

    due_at = timezone.now() + timedelta(hours=RELANCE_DELAY_HOURS)

    # --------------------------------------------------
    # Création de la tâche
    # --------------------------------------------------

    task = LeadTask.objects.create(
        lead=lead,
        task_type=task_type,
        status=task_status,
        title=f"Relance — absent au RDV du {lead.appointment_date.strftime('%d/%m/%Y à %Hh%M') if lead.appointment_date else 'RDV'}",
        description=(
            f"Le lead n'était pas présent à son rendez-vous.\n"
            f"À rappeler rapidement pour reprogrammer un RDV."
        ),
        due_at=due_at,
        triggered_by_event=triggered_by_event,
        metadata={
            "auto_created":       True,
            "trigger":            "ABSENT",
            "appointment_date":   lead.appointment_date.isoformat() if lead.appointment_date else None,
        },
    )

    logger.info(
        "[create_absent_followup_task] Tâche RELANCE_LEAD créée : task_id=%s | lead_id=%s | due_at=%s",
        task.id, lead_id, due_at,
    )