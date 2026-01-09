import logging
from celery import shared_task

from api.appointment.models import Appointment
from api.leads.models import Lead
from api.utils.email.appointment.notifications import (
    send_appointment_created_email,
    send_appointment_deleted_email,
    send_appointment_updated_email,
)

logger = logging.getLogger(__name__)


@shared_task(queue="emails")
def send_appointment_created_task(appointment_id: int):
    """
    Envoie un email au lead pour l’informer de la création du rendez-vous.
    """
    appointment = (
        Appointment.objects.select_related("lead")
        .filter(id=appointment_id)
        .first()
    )

    if appointment and appointment.lead and appointment.lead.email:
        send_appointment_created_email(appointment.lead, appointment)
        logger.info(
            f"📅 Email de création de RDV envoyé à "
            f"{appointment.lead.email} (lead #{appointment.lead.id})"
        )
    else:
        logger.warning(
            f"❌ RDV non envoyé : lead ou email manquant "
            f"pour appointment #{appointment_id}"
        )


@shared_task(queue="email")
def send_appointment_updated_task(appointment_id: int):
    """
    Envoie un email au lead pour l’informer de la modification du rendez-vous.
    """
    appointment = (
        Appointment.objects.select_related("lead")
        .filter(id=appointment_id)
        .first()
    )

    if appointment and appointment.lead and appointment.lead.email:
        send_appointment_updated_email(appointment.lead, appointment)
        logger.info(
            f"✏️ Email de modification de RDV envoyé à "
            f"{appointment.lead.email} (lead #{appointment.lead.id})"
        )
    else:
        logger.warning(
            f"❌ RDV modifié non envoyé : lead ou email manquant "
            f"pour appointment #{appointment_id}"
        )


@shared_task(queue="email")
def send_appointment_deleted_task(lead_id: int, appointment_data: dict):
    """
    Envoie un email pour informer qu’un rendez-vous a été annulé.
    Toutes les données sont passées, car le RDV est supprimé.
    """
    from django.utils.dateparse import parse_datetime

    try:
        lead = Lead.objects.get(pk=lead_id)
        appointment_date = parse_datetime(appointment_data["date"])

        send_appointment_deleted_email(
            lead,
            appointment_date,
            appointment_data,
        )

        logger.info(
            f"🗑️ Email d’annulation de RDV envoyé à "
            f"{lead.email} (lead #{lead.id})"
        )

    except Exception:
        logger.error(
            f"❌ Erreur lors de l’envoi du mail d’annulation "
            f"pour lead #{lead_id}",
            exc_info=True,
        )