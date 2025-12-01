# api/utils/email/notifications.py
from api.utils.email import send_html_email
from api.utils.email.config import TDS_FRANCE_ADDRESS, _base_context, _build_context
from api.utils.email.utils import _name_from_user, get_french_datetime_strings


def send_jurist_appointment_email(jurist_appointment):
    lead = jurist_appointment.lead
    jurist = jurist_appointment.jurist

    context = _build_context(
        lead=lead,
        dt=jurist_appointment.date,
        location=TDS_FRANCE_ADDRESS,
        appointment=jurist_appointment,
        is_jurist=True,
        extra={"jurist": jurist},
    )

    send_html_email(
        to_email=lead.email,
        subject="Confirmation : rendez-vous juriste planifié – TDS France",
        template_name="email/jurist_appointment/jurist_appointment_planned.html",
        context=context,
    )


def send_jurist_appointment_deleted_email(lead, jurist, appointment_date):
    date_str, time_str = get_french_datetime_strings(appointment_date)

    context = {
        **_base_context(lead),
        "jurist": jurist,
        "appointment": {
            "date": date_str,
            "time": time_str,
            "location": TDS_FRANCE_ADDRESS,
            "with_label": "Juriste",
            "with_name": _name_from_user(jurist) or "",
        },
    }

    send_html_email(
        to_email=lead.email,
        subject="Votre rendez-vous juriste a été annulé – TDS France",
        template_name="email/jurist_appointment/jurist_appointment_deleted.html",
        context=context,
    )
