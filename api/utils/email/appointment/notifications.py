from api.utils.email import send_html_email
from api.utils.email.config import COMPANY_ADDRESS, _build_context


def send_appointment_created_email(lead, appointment):
    """
    Envoie un e-mail pour informer qu’un rendez-vous a été créé.
    """
    context = _build_context(
        lead=lead,
        dt=appointment.date,
        location=COMPANY_ADDRESS,
        appointment=appointment,
    )

    return send_html_email(
        to_email=lead.email,
        subject=f"Nouveau rendez-vous planifié – {context['company']['name']}",
        template_name="email/appointment/appointment_created.html",
        context=context,
    )


def send_appointment_updated_email(lead, appointment):
    """
    Envoie un e-mail pour informer qu’un rendez-vous a été modifié.
    """
    context = _build_context(
        lead=lead,
        dt=appointment.date,
        location=COMPANY_ADDRESS,
        appointment=appointment,
    )

    return send_html_email(
        to_email=lead.email,
        subject=f"Mise à jour de votre rendez-vous – {context['company']['name']}",
        template_name="email/appointment/appointment_updated.html",
        context=context,
    )


def send_appointment_deleted_email(lead, appointment_date, appointment_data: dict):
    """
    Envoie un e-mail pour informer qu’un rendez-vous a été annulé.
    `appointment_data` peut être un objet ou un dictionnaire.
    """
    context = _build_context(
        lead=lead,
        dt=appointment_date,
        location=COMPANY_ADDRESS,
        appointment=appointment_data,
    )

    return send_html_email(
        to_email=lead.email,
        subject=f"Rendez-vous annulé – {context['company']['name']}",
        template_name="email/appointment/appointment_deleted.html",
        context=context,
    )
