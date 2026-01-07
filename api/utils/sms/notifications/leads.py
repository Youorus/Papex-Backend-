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
        f"Bonjour {lead.first_name},\n"
        f"Votre rendez-vous avec Papiers Express est confirmé.\n\n"
        f"Le {date_str} à {time_str}\n"
        f"au 39 rue Navier, 75017 Paris\n"
        f"Tél : 06 31 01 84 26\n\n"
        f"À bientôt,\n"
        f"Papiers Express"
    )

    return send_sms(
        message=message,
        receivers=[lead.phone],
    )
