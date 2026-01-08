# api/utils/sms/notifications/leads.py

from api.utils.sms.sender import send_sms
from api.utils.sms.utils import get_french_datetime_strings_sms
import unicodedata


# =========================
# Constantes SMS
# =========================
COMPANY_NAME = "Papiers Express"
COMPANY_PHONE = "0142596008"
COMPANY_ADDRESS_LINE_1 = "39 rue Navier"
COMPANY_ADDRESS_LINE_2 = "Paris 17"

SMS_MAX_LENGTH = 140


def normalize_sms(text: str) -> str:
    """
    Supprime accents et caracteres non GSM
    """
    return (
        unicodedata.normalize("NFKD", text)
        .encode("ascii", "ignore")
        .decode("ascii")
    )


def send_appointment_confirmation_sms(lead):
    """
    SMS de confirmation de rendez-vous
    1 SMS / 1 credit garanti
    """
    if not lead.phone or not lead.appointment_date:
        return

    # Date courte et SMS-friendly
    date_str, time_str = get_french_datetime_strings_sms(lead.appointment_date)

    message = (
        "Rendez-vous confirme\n"
        f"{COMPANY_NAME}\n\n"
        f"{date_str} {time_str}\n"
        f"{COMPANY_ADDRESS_LINE_1}\n"
        f"{COMPANY_ADDRESS_LINE_2}\n\n"
        f"Tel {COMPANY_PHONE}"
    )

    message = normalize_sms(message)

    # Sécurité ultime : 1 SMS max
    if len(message) > SMS_MAX_LENGTH:
        raise ValueError("SMS trop long pour 1 credit")

    return send_sms(
        message=message,
        receivers=[lead.phone],
    )

def send_appointment_reminder_sms(lead):
    """
    SMS de rappel de rendez-vous
    1 SMS / 1 credit garanti
    """
    if not lead.phone or not lead.appointment_date:
        return

    date_str, time_str = get_french_datetime_strings_sms(lead.appointment_date)

    message = (
        "Rappel rendez-vous\n"
        f"{COMPANY_NAME}\n\n"
        f"{date_str} {time_str}\n"
        f"{COMPANY_ADDRESS_LINE_1}\n"
        f"{COMPANY_ADDRESS_LINE_2}\n\n"
        f"Tel {COMPANY_PHONE}"
    )

    message = normalize_sms(message)

    if len(message) > SMS_MAX_LENGTH:
        raise ValueError("SMS trop long pour 1 credit")

    return send_sms(
        message=message,
        receivers=[lead.phone],
    )