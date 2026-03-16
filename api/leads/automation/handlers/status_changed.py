# api/leads/automation/handlers/status_changed.py

import logging

from api.leads.constants import (
    RDV_A_CONFIRMER,
    RDV_CONFIRME,
    ABSENT,
    PRESENT,
    # À créer en base + dans constants.py quand le statut sera défini :
    # CONTRAT_SIGNE,
    # INJOIGNABLE,
)

from api.sms.tasks import (
    send_appointment_confirmation_sms_task,
    send_absent_urgency_sms_task,
    send_present_no_contract_sms_task,
    # send_contract_signed_sms_task,      # activer quand CONTRAT_SIGNE créé
)

# ⚠️ create_absent_followup_task N'EST PAS importé ici
# Import local dans le bloc ABSENT — évite le circular import :
# leads_events/models → engine → registry → status_changed
#   → leads_task/tasks → leads_task/models → leads_events/models

# from api.whatsapp.tasks import (
#     send_welcome_whatsapp_task,
#     send_absent_urgency_whatsapp_task,
#     send_present_no_contract_whatsapp_task,
#     send_contract_signed_whatsapp_task,
# )

# from api.email.tasks import (
#     send_welcome_email_task,
#     send_absent_urgency_email_task,
#     send_present_no_contract_email_task,
#     send_contract_signed_email_task,
# )

logger = logging.getLogger(__name__)

# Délai avant envoi des messages post-RDV (en secondes)
POST_RDV_DELAY = 60 * 60 * 2  # 2h


def handle_status_changed(event):

    data        = event.data
    lead        = event.lead
    from_status = data.get("from")
    to_status   = data.get("to")

    logger.info(
        "[handle_status_changed] lead_id=%s | %s → %s",
        lead.id, from_status, to_status,
    )

    # --------------------------------------------------
    # RDV_A_CONFIRMER
    # Cas : report ou reprogrammation d'un RDV existant.
    # → SMS confirmation si date a changé
    #   (anti-doublon via LeadEvent APPOINTMENT_CONFIRMATION_SENT)
    # --------------------------------------------------

    if to_status == RDV_A_CONFIRMER:

        send_appointment_confirmation_sms_task.delay(lead.id)

        logger.info(
            "[handle_status_changed] Task SMS confirmation dispatchée : lead_id=%s",
            lead.id,
        )

        # send_welcome_whatsapp_task.delay(lead.id)
        # send_welcome_email_task.delay(lead.id)

    # --------------------------------------------------
    # RDV_CONFIRME
    # Cas : le lead a confirmé sa présence au RDV.
    # → WhatsApp + email bienvenue détaillant le service
    #   (SMS déjà envoyé à la création — pas de doublon ici)
    # --------------------------------------------------

    elif to_status == RDV_CONFIRME:

        logger.info(
            "[handle_status_changed] RDV confirmé — notifications bienvenue : lead_id=%s",
            lead.id,
        )

        # send_welcome_whatsapp_task.delay(lead.id)
        # send_welcome_email_task.delay(lead.id)

    # --------------------------------------------------
    # ABSENT
    # Cas : le lead ne s'est pas présenté à son RDV.
    #
    # Séquence déclenchée :
    #   1. SMS urgence absence             → immédiat
    #   2. Tâche RELANCE_LEAD              → échéance +2h
    #   3. WhatsApp urgence (à implémenter)
    #   4. Email urgence (à implémenter)
    # --------------------------------------------------

    elif to_status == ABSENT:

        # 1. SMS urgence
        send_absent_urgency_sms_task.delay(lead.id)

        logger.info(
            "[handle_status_changed] Task SMS absent urgence dispatchée : lead_id=%s",
            lead.id,
        )

        # 2. Tâche de relance commerciale — échéance +2h
        #    Import local obligatoire pour éviter le circular import
        from api.leads_task.tasks import create_absent_followup_task

        create_absent_followup_task.delay(
            lead_id=lead.id,
            triggered_event_id=event.id,
        )

        logger.info(
            "[handle_status_changed] Task RELANCE_LEAD dispatchée : lead_id=%s",
            lead.id,
        )

        # 3. WhatsApp urgence (à implémenter)
        # send_absent_urgency_whatsapp_task.delay(lead.id)

        # 4. Email urgence (à implémenter)
        # send_absent_urgency_email_task.delay(lead.id)

    # --------------------------------------------------
    # PRESENT (sans contrat signé)
    # Cas : le lead est venu au RDV mais n'a pas signé.
    # → SMS + WhatsApp + email motivation / avis Google
    #   Envoyés avec un délai de 2h après le RDV.
    # --------------------------------------------------

    elif to_status == PRESENT:

        send_present_no_contract_sms_task.apply_async(
            args=[lead.id],
            countdown=POST_RDV_DELAY,
        )

        logger.info(
            "[handle_status_changed] Task SMS présent planifiée +2h : lead_id=%s",
            lead.id,
        )

        # send_present_no_contract_whatsapp_task.apply_async(
        #     args=[lead.id],
        #     countdown=POST_RDV_DELAY,
        # )
        # send_present_no_contract_email_task.apply_async(
        #     args=[lead.id],
        #     countdown=POST_RDV_DELAY,
        # )

    # --------------------------------------------------
    # CONTRAT_SIGNE  (statut à créer)
    # --------------------------------------------------

    # elif to_status == CONTRAT_SIGNE:
    #
    #     send_contract_signed_sms_task.apply_async(
    #         args=[lead.id],
    #         countdown=POST_RDV_DELAY,
    #     )
    #     # send_contract_signed_whatsapp_task.apply_async(...)
    #     # send_contract_signed_email_task.apply_async(...)

    # --------------------------------------------------
    # INJOIGNABLE  (statut à créer)
    # --------------------------------------------------

    # elif to_status == INJOIGNABLE:
    #     logger.info(
    #         "[handle_status_changed] Lead INJOIGNABLE — automatisations stoppées : lead_id=%s",
    #         lead.id,
    #     )

    # --------------------------------------------------
    # Statut non géré par l'automation
    # --------------------------------------------------

    else:

        logger.debug(
            "[handle_status_changed] Statut '%s' non géré par l'automation : lead_id=%s",
            to_status, lead.id,
        )