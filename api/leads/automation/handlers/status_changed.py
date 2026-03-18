# api/leads/automation/handlers/status_changed.py

import logging

from api.leads.constants import (
    RDV_A_CONFIRMER,
    RDV_CONFIRME,
    ABSENT,
    PRESENT,
    # CONTRAT_SIGNE,  # Décommenter quand créé en base
)

from api.sms.tasks import (
    send_appointment_confirmation_sms_task,
    send_absent_urgency_sms_task,
    send_present_no_contract_sms_task,
    # send_contract_signed_sms_task,  # Décommenter quand prêt
)

logger = logging.getLogger(__name__)

# Délai avant envoi des messages post-RDV (2 heures)
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
    # 1. RDV_A_CONFIRMER (Report ou Nouveau RDV)
    # --------------------------------------------------
    if to_status == RDV_A_CONFIRMER:
        # Envoi immédiat du SMS de confirmation
        send_appointment_confirmation_sms_task.delay(lead.id)

        logger.info(
            "[handle_status_changed] Task SMS confirmation dispatchée : lead_id=%s",
            lead.id,
        )

    # --------------------------------------------------
    # 2. RDV_CONFIRME (Le lead a validé sa venue)
    # --------------------------------------------------
    elif to_status == RDV_CONFIRME:
        logger.info(
            "[handle_status_changed] RDV confirmé — lead_id=%s",
            lead.id,
        )
        # Ici, on laisse le Celery Beat prendre le relais pour les rappels J-2 / J-1

    # --------------------------------------------------
    # 3. ABSENT (Le lead ne s'est pas présenté)
    # --------------------------------------------------
    elif to_status == ABSENT:
        # A. SMS URGENCE : Envoi immédiat ("On vous attendait...")
        send_absent_urgency_sms_task.delay(lead.id)

        logger.info(
            "[handle_status_changed] Task SMS absent urgence dispatchée : lead_id=%s",
            lead.id,
        )

        # B. TÂCHE CRM : Création d'une tâche de rappel pour le commercial (+2h)
        # Import local pour éviter le circular import (models -> engine -> tasks -> models)
        try:
            from api.leads_task.tasks import create_absent_followup_task
            create_absent_followup_task.delay(
                lead_id=lead.id,
                triggered_event_id=event.id,
            )
            logger.info("[handle_status_changed] Tâche CRM Relance créée : lead_id=%s", lead.id)
        except ImportError:
            logger.error("[handle_status_changed] Impossible d'importer create_absent_followup_task")

    # --------------------------------------------------
    # 4. PRESENT (Venu en RDV mais sans signature immédiate)
    # --------------------------------------------------
    elif to_status == PRESENT:
        # Envoi d'un SMS de motivation / avis 2h après le RDV
        send_present_no_contract_sms_task.apply_async(
            args=[lead.id],
            countdown=POST_RDV_DELAY,
        )

        logger.info(
            "[handle_status_changed] Task SMS relance PRESENT planifiée (+2h) : lead_id=%s",
            lead.id,
        )

    # --------------------------------------------------
    # 5. Statut non géré par l'automation
    # --------------------------------------------------
    else:
        logger.debug(
            "[handle_status_changed] Statut '%s' ignoré par l'automation : lead_id=%s",
            to_status, lead.id,
        )