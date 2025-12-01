import logging

from celery import shared_task

from api.leads.models import Lead
from api.utils.email import send_appointment_confirmation_email
from api.utils.email.leads.notifications import (
    send_appointment_planned_email,
    send_dossier_status_email,
    send_formulaire_email,
    send_jurist_assigned_email
)

logger = logging.getLogger(__name__)


@shared_task
def send_appointment_confirmation_task(lead_id: int):
    lead = Lead.objects.select_related("status").filter(id=lead_id).first()
    if lead and lead.email:
        send_appointment_confirmation_email(lead)
        logger.info(f"📧 Confirmation envoyée à {lead.email} (lead #{lead.id})")
    else:
        logger.warning(
            f"❌ Aucune confirmation envoyée (lead #{lead_id} inexistant ou sans email)"
        )


@shared_task
def send_appointment_planned_task(lead_id: int):
    lead = Lead.objects.select_related("status").filter(id=lead_id).first()
    if lead and lead.email:
        send_appointment_planned_email(lead)
        logger.info(f"📅 RDV planifié envoyé à {lead.email} (lead #{lead.id})")
    else:
        logger.warning(
            f"❌ RDV planifié non envoyé (lead #{lead_id} inexistant ou sans email)"
        )


@shared_task
def send_dossier_status_notification_task(lead_id: int):
    lead = Lead.objects.select_related("statut_dossier").filter(id=lead_id).first()
    if lead and lead.statut_dossier:
        send_dossier_status_email(lead)
        logger.info(
            f"📨 Statut dossier '{lead.statut_dossier.label}' envoyé pour lead #{lead.id}"
        )
    else:
        logger.warning(
            f"❌ Notification de statut dossier non envoyée (lead #{lead_id} ou statut manquant)"
        )


"""
Tâche asynchrone envoyant un e-mail au lead contenant le lien vers le formulaire à compléter.

Cette tâche est appelée après la création du lead ou lorsqu’une action nécessite que le client
remplisse ou mette à jour un formulaire d'information.
"""


@shared_task
def send_formulaire_task(lead_id: int):
    lead = Lead.objects.filter(id=lead_id).first()
    if lead:
        send_formulaire_email(lead)
        logger.info(f"📤 Formulaire envoyé pour lead #{lead.id}")
    else:
        logger.warning(f"❌ Formulaire non envoyé (lead #{lead_id} introuvable)")



@shared_task
def send_jurist_assigned_notification_task(lead_id: int, jurist_id: int):
    from api.leads.models import Lead
    from api.users.models import User
    from api.utils.email.leads.notifications import send_jurist_assigned_email

    lead = Lead.objects.filter(id=lead_id).first()
    jurist = User.objects.filter(id=jurist_id).first()

    if lead and jurist and lead.email:
        send_jurist_assigned_email(lead, jurist)
        logger.info(f"📩 Juriste assigné notifié pour lead #{lead.id} ({lead.email})")
    else:
        logger.warning(f"❌ Notification juriste non envoyée (lead #{lead_id}, juriste #{jurist_id})")