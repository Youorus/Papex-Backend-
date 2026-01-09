# api/utils/sms/notifications/leads.py

from api.sms.sender import send_sms
from api.sms.utils import get_french_datetime_strings_sms
import unicodedata

# =========================
# Constantes SMS
# =========================
COMPANY_NAME = "Papiers Express"
COMPANY_PHONE = "0142596008"
COMPANY_ADDRESS_SHORT = "39 rue Navier, 75017"  # Version courte

SMS_MAX_LENGTH = 160  # Pour GSM 7-bit (sans caractères étendus)


def normalize_sms(text: str) -> str:
    """
    Normalise le texte pour le GSM 7-bit alphabet
    Supprime accents et caractères non-standard
    """
    # Normalisation Unicode
    text = unicodedata.normalize('NFKD', text)

    # Table de substitution pour caractères français courants
    replacements = {
        'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
        'à': 'a', 'â': 'a', 'ä': 'a',
        'î': 'i', 'ï': 'i',
        'ô': 'o', 'ö': 'o',
        'ù': 'u', 'û': 'u', 'ü': 'u',
        'ç': 'c',
        'É': 'E', 'È': 'E', 'Ê': 'E', 'Ë': 'E',
        'À': 'A', 'Â': 'A', 'Ä': 'A',
        'Î': 'I', 'Ï': 'I',
        'Ô': 'O', 'Ö': 'O',
        'Ù': 'U', 'Û': 'U', 'Ü': 'U',
        'Ç': 'C',
        '«': '"', '»': '"', '€': 'EUR'
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    # Suppression des caractères restants non-ASCII
    text = text.encode('ascii', 'ignore').decode('ascii')

    return text


def validate_sms_length(message: str) -> str:
    """
    Valide et ajuste si nécessaire pour garantir 1 SMS max
    """
    if len(message) <= SMS_MAX_LENGTH:
        return message

    # Version raccourcie si trop long
    shortened = message

    # 1. Raccourcir l'adresse
    shortened = shortened.replace(COMPANY_ADDRESS_SHORT, "Paris 17")

    # 2. Raccourcir le nom si nécessaire
    if len(shortened) > SMS_MAX_LENGTH:
        shortened = shortened.replace(COMPANY_NAME, "Papiers Exp")

    # 3. Format minimaliste si toujours trop long
    if len(shortened) > SMS_MAX_LENGTH:
        # Format ultra court
        date_str, time_str = get_french_datetime_strings_sms(lead.appointment_date)
        shortened = f"RDV {date_str} {time_str}. {COMPANY_NAME} {COMPANY_ADDRESS_SHORT}. Tel:{COMPANY_PHONE}"
        shortened = normalize_sms(shortened)

    if len(shortened) > SMS_MAX_LENGTH:
        raise ValueError(f"SMS trop long après optimisation: {len(shortened)} caractères")

    return shortened


def send_appointment_confirmation_sms(lead):
    """
    SMS de confirmation de rendez-vous - 1 SMS / 1 crédit garanti
    Format strict GSM 7-bit
    """
    if not lead.phone or not lead.appointment_date:
        return

    date_str, time_str = get_french_datetime_strings_sms(lead.appointment_date)

    # Format professionnel standard sans emojis
    message = (
        f"RDV CONFIRME\n"
        f"{COMPANY_NAME}\n"
        f"Le {date_str} a {time_str}\n"
        f"{COMPANY_ADDRESS_SHORT}\n\n"
        f"Tel: {COMPANY_PHONE}\n"
        f"Merci de votre confiance"
    )

    message = normalize_sms(message)
    message = validate_sms_length(message)

    return send_sms(
        message=message,
        receivers=[lead.phone],
    )


def send_appointment_reminder_sms(lead):
    """
    SMS de rappel de rendez-vous - 1 SMS / 1 crédit garanti
    Format strict GSM 7-bit
    """
    if not lead.phone or not lead.appointment_date:
        return

    date_str, time_str = get_french_datetime_strings_sms(lead.appointment_date)

    # Format professionnel standard sans emojis
    message = (
        f"RAPPEL RDV\n"
        f"{COMPANY_NAME}\n"
        f"Le {date_str} a {time_str}\n"
        f"{COMPANY_ADDRESS_SHORT}\n"
        f"Tel: {COMPANY_PHONE}\n"
        f"A bientot"
    )

    message = normalize_sms(message)
    message = validate_sms_length(message)

    return send_sms(
        message=message,
        receivers=[lead.phone],
    )


# Version alternative ultra-conforme (toujours < 140 caractères)
def send_appointment_sms_safe(lead, sms_type="confirmation"):
    """
    Version ultra-safe garantie < 140 caractères
    """
    if not lead.phone or not lead.appointment_date:
        return

    date_str, time_str = get_french_datetime_strings_sms(lead.appointment_date)

    if sms_type == "confirmation":
        message = (
            f"RDV confirme le {date_str} {time_str}. "
            f"{COMPANY_NAME}, {COMPANY_ADDRESS_SHORT}. "
            f"Tel: {COMPANY_PHONE}. Merci."
        )
    else:
        message = (
            f"Rappel: RDV le {date_str} {time_str}. "
            f"{COMPANY_NAME}, {COMPANY_ADDRESS_SHORT}. "
            f"Tel: {COMPANY_PHONE}."
        )

    message = normalize_sms(message)

    # Cette version fait ~110-120 caractères
    return send_sms(
        message=message,
        receivers=[lead.phone],
    )