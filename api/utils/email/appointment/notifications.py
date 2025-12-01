from api.utils.email import send_html_email
from api.utils.email.config import TDS_FRANCE_ADDRESS, _build_context


def send_appointment_created_email(lead, appointment):
    """
    Envoie un e-mail pour informer qu’un rendez-vous a été créé.
    """
    context = _build_context(
        lead,
        appointment.date,
        TDS_FRANCE_ADDRESS,
        appointment=appointment,
    )
    return send_html_email(
        to_email=lead.email,
        subject="Nouveau rendez-vous planifié – TDS France",
        template_name="email/appointment/appointment_created.html",
        context=context,
    )


def send_appointment_updated_email(lead, appointment):
    """
    Envoie un e-mail pour informer qu’un rendez-vous a été modifié.
    """
    context = _build_context(
        lead,
        appointment.date,
        TDS_FRANCE_ADDRESS,
        appointment=appointment,
    )
    return send_html_email(
        to_email=lead.email,
        subject="Mise à jour de votre rendez-vous – TDS France",
        template_name="email/appointment/appointment_updated.html",
        context=context,
    )


def send_appointment_deleted_email(lead, appointment_date, appointment_data: dict):
    """
    Envoie un e-mail pour informer qu’un rendez-vous a été annulé.
    """
    context = _build_context(
        lead,
        appointment_date,
        TDS_FRANCE_ADDRESS,
        appointment=appointment_data,  # ← dict au lieu d’objet
    )
    return send_html_email(
        to_email=lead.email,
        subject="Rendez-vous annulé – TDS France",
        template_name="email/appointment/appointment_deleted.html",
        context=context,
    )
