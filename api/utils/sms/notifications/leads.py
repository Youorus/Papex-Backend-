# api/utils/sms/notifications/leads.py

from api.utils.sms.sender import send_sms
from api.utils.email.utils import get_french_datetime_strings


def send_appointment_confirmation_sms(lead):
    """
    SMS de confirmation de rendez-vous
    """
    if not lead.phone:
        return

    date_str, time_str = get_french_datetime_strings(lead.appointment_date)

    message = (
        f"Bonjour {lead.first_name}, "
        f"Votre rendez vous avec Papiers Express est confirme "
        f"le {date_str} a {time_str}. "
        f"Adresse: 39 rue Navier 75017 Paris. "
        f"Tel 0631018426. "
        f"A bientot. "
        f"Papiers Express."
    )

    return send_sms(
        message=message,
        receivers=[lead.phone],
    )
