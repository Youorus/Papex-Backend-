# api/utils/email/notifications.py

from api.utils.email import send_html_email
from api.utils.email.config import COMPANY_ADDRESS, _base_context, _build_context
from api.utils.email.utils import _name_from_user, get_french_datetime_strings


def send_jurist_appointment_email(jurist_appointment):
    """
    Envoie l’email au lead pour confirmer un rendez-vous
    planifié avec le juriste.
    """
    lead = jurist_appointment.lead
    jurist = jurist_appointment.jurist

    context = _build_context(
        lead=lead,
        dt=jurist_appointment.date,
        location=COMPANY_ADDRESS,
        appointment=jurist_appointment,
        is_jurist=True,
        extra={"jurist": jurist},
    )

    return send_html_email(
        to_email=lead.email,
        subject=f"Confirmation : rendez-vous avec votre juriste – {context['company']['name']}",
        template_name="email/jurist_appointment/jurist_appointment_planned.html",
        context=context,
    )


def send_jurist_appointment_deleted_email(lead, jurist, appointment_date):
    """
    Envoie l'email au lead lorsque son rendez-vous juriste est annulé.
    """
    date_str, time_str = get_french_datetime_strings(appointment_date)

    # On construit le contexte unifié
    context = _build_context(
        lead=lead,
        extra={
            "jurist": jurist,
            "appointment": {
                "date": date_str,
                "time": time_str,
                "location": COMPANY_ADDRESS,
                "with_label": "Juriste",
                "with_name": _name_from_user(jurist) or "",
            },
        },
    )

    return send_html_email(
        to_email=lead.email,
        subject=f"Annulation du rendez-vous juriste – {context['company']['name']}",
        template_name="email/jurist_appointment/jurist_appointment_deleted.html",
        context=context,
    )
