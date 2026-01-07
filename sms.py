from api.utils.sms.sender import send_sms
from api.utils.email.utils import get_french_datetime_strings
import unicodedata


def _to_gsm(text: str) -> str:
    """
    Force un texte 100% GSM 7 bits (OVH safe)
    """
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    return text


def send_appointment_confirmation_sms(lead):
    """
    SMS de confirmation de rendez-vous
    - 100% GSM
    - 1 seul SMS garanti
    - compatible OVH
    """
    if not lead.phone:
        return

    date_str, time_str = get_french_datetime_strings(lead.appointment_date)

    first_name = _to_gsm(lead.first_name or "")

    date_str = _to_gsm(date_str)
    time_str = _to_gsm(time_str)

    message = (
        f"Bonjour {first_name}, "
        f"Votre rendez vous avec Papiers Express est confirme "
        f"le {date_str} a {time_str}. "
        f"Adresse: 39 rue Navier 75017 Paris. "
        f"Tel 0631018426. "
        f"A bientot. "
        f"Papiers Express."
    )

    message = _to_gsm(message)

    return send_sms(
        message=message,
        receivers=[lead.phone],
    )
