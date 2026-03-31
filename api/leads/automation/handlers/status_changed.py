# api/leads/automation/handlers/status_changed.py
# ✅ Migré de Celery (.delay / .apply_async) vers Django-Q2 (appels directs aux dispatchers)

import logging

from api.leads.constants import (
    RDV_A_CONFIRMER,
    RDV_CONFIRME,
    ABSENT,
    PRESENT,
)

from api.sms.tasks import (
    send_appointment_confirmation_sms_task,
    send_absent_urgency_sms_task,
    send_present_no_contract_sms_task,
)

logger = logging.getLogger(__name__)

# Délai avant envoi des messages post-RDV (2 heures en secondes)
POST_RDV_DELAY = 60 * 60 * 2


def handle_status_changed(event):
    """
    Orchestrateur des automatisations suite à un changement de statut.
    """
    data        = event.data
    lead        = event.lead
    from_status = data.get("from")
    to_status   = data.get("to")

    logger.info(
        "[handle_status_changed] lead_id=%s | %s → %s",
        lead.id, from_status, to_status,
    )

    # --------------------------------------------------
    # 1. RDV_A_CONFIRMER
    # --------------------------------------------------
    if to_status == RDV_A_CONFIRMER:
        # ✅ Django-Q2 : dispatch via la fonction publique (plus de .delay())
        send_appointment_confirmation_sms_task(lead.id)

        logger.info(
            "[handle_status_changed] SMS confirmation dispatché : lead_id=%s",
            lead.id,
        )

    # --------------------------------------------------
    # 2. RDV_CONFIRME
    # --------------------------------------------------
    elif to_status == RDV_CONFIRME:
        logger.info(
            "[handle_status_changed] RDV confirmé — lead_id=%s",
            lead.id,
        )

    # --------------------------------------------------
    # 3. ABSENT
    # --------------------------------------------------
    elif to_status == ABSENT:
        # A. SMS URGENCE — immédiat
        send_absent_urgency_sms_task(lead.id)

        logger.info(
            "[handle_status_changed] SMS absent urgence dispatché : lead_id=%s",
            lead.id,
        )

        # B. TÂCHE CRM — création en arrière-plan
        try:
            from api.leads_task.tasks import create_absent_followup_task
            create_absent_followup_task(
                lead_id=lead.id,
                triggered_event_id=event.id,
            )
            logger.info(
                "[handle_status_changed] Tâche CRM Relance dispatchée : lead_id=%s",
                lead.id,
            )
        except ImportError:
            logger.error(
                "[handle_status_changed] Impossible d'importer create_absent_followup_task"
            )

    # --------------------------------------------------
    # 4. PRESENT
    # --------------------------------------------------
    elif to_status == PRESENT:
        # ✅ Django-Q2 : countdown géré via le paramètre countdown= du dispatcher
        send_present_no_contract_sms_task(lead.id, countdown=POST_RDV_DELAY)

        logger.info(
            "[handle_status_changed] SMS relance PRESENT planifié (+2h) : lead_id=%s",
            lead.id,
        )

    # --------------------------------------------------
    # 5. Statut non géré
    # --------------------------------------------------
    else:
        logger.debug(
            "[handle_status_changed] Statut '%s' ignoré par l'automation : lead_id=%s",
            to_status, lead.id,
        )