# api/utils/email/jurist_appointment/tasks.py

import logging
from datetime import datetime

from celery import shared_task

from api.jurist_appointment.models import JuristAppointment
from api.leads.models import Lead
from api.users.models import User
from api.utils.email.jurist_appointment.notifications import (
    send_jurist_appointment_email,
    send_jurist_appointment_deleted_email,
)

logger = logging.getLogger(__name__)


@shared_task(queue="email")
def send_jurist_appointment_created_task(appointment_id: int):
    """
    Envoie un e-mail de confirmation de rendez-vous juriste.
    """
    appointment = (
        JuristAppointment.objects
        .select_related("lead")
        .filter(id=appointment_id)
        .first()
    )

    if not appointment:
        logger.warning(
            f"❌ JuristAppointment #{appointment_id} introuvable"
        )
        return

    send_jurist_appointment_email(appointment)
    logger.info(
        f"⚖️ Email RDV juriste envoyé (appointment #{appointment.id})"
    )


@shared_task(queue="email")
def send_jurist_appointment_deleted_task(
    lead_id: int,
    jurist_id: int,
    date_str: str,
):
    """
    Envoie un e-mail d’annulation de rendez-vous juriste.
    """
    try:
        lead = Lead.objects.get(id=lead_id)
        jurist = User.objects.get(id=jurist_id)
        date = datetime.fromisoformat(date_str)

        send_jurist_appointment_deleted_email(lead, jurist, date)

        logger.info(
            f"⚖️ Email annulation RDV juriste envoyé "
            f"(lead #{lead_id}, juriste #{jurist_id})"
        )

    except (Lead.DoesNotExist, User.DoesNotExist, ValueError) as e:
        logger.error(
            "❌ Erreur email annulation RDV juriste",
            exc_info=e,
        )