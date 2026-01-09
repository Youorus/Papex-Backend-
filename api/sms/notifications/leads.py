# api/utils/sms/notifications/leads.py

from api.sms.sender import send_sms
from api.sms.utils import get_french_datetime_strings_sms
import unicodedata
import re

# =========================
# Constantes SMS
# =========================
COMPANY_NAME = "Papiers Express"
COMPANY_PHONE = "0142596008"
COMPANY_ADDRESS_SHORT = "39 rue Navier, 75017"

SMS_MAX_LENGTH = 160  # GSM 7-bit


# ======================================================
# 📞 Normalisation téléphone (OBLIGATOIRE OVH)
# ======================================================
def normalize_phone(phone: str) -> str:
    """
    Normalise un numéro FR vers le format E.164 (+336XXXXXXXX)
    """
    if not phone:
        return ""

    phone = phone.strip()
    phone = re.sub(r"[^\d+]", "", phone)

    # 06XXXXXXXX → +336XXXXXXXX
    if phone.startswith("0"):
        phone = "+33" + phone[1:]

    # 336XXXXXXXX → +336XXXXXXXX
    elif phone.startswith("33"):
        phone = "+" + phone

    # Si déjà en +33, OK
    elif phone.startswith("+33"):
        pass

    return phone


# ======================================================
# ✍️ Normalisation texte GSM 7-bit
# ======================================================
def normalize_sms(text: str) -> str:
    """
    Normalise le texte pour GSM 7-bit
    """
    text = unicodedata.normalize("NFKD", text)

    replacements = {
        "é": "e", "è": "e", "ê": "e", "ë": "e",
        "à": "a", "â": "a", "ä": "a",
        "î": "i", "ï": "i",
        "ô": "o", "ö": "o",
        "ù": "u", "û": "u", "ü": "u",
        "ç": "c",
        "É": "E", "È": "E", "Ê": "E", "Ë": "E",
        "À": "A", "Â": "A", "Ä": "A",
        "Î": "I", "Ï": "I",
        "Ô": "O", "Ö": "O",
        "Ù": "U", "Û": "U", "Ü": "U",
        "Ç": "C",
        "«": '"', "»": '"', "€": "EUR",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return text.encode("ascii", "ignore").decode("ascii")


# ======================================================
# 📏 Validation longueur SMS
# ======================================================
def validate_sms_length(message: str) -> str:
    if len(message) <= SMS_MAX_LENGTH:
        return message

    shortened = message.replace(COMPANY_ADDRESS_SHORT, "Paris 17")

    if len(shortened) > SMS_MAX_LENGTH:
        shortened = shortened.replace(COMPANY_NAME, "Papiers Exp")

    if len(shortened) > SMS_MAX_LENGTH:
        raise ValueError(
            f"SMS trop long après optimisation ({len(shortened)} caractères)"
        )

    return shortened


# ======================================================
# 📲 SMS CONFIRMATION RDV
# ======================================================
def send_appointment_confirmation_sms(lead):
    if not lead.phone or not lead.appointment_date:
        return

    phone = normalize_phone(lead.phone)
    if not phone:
        return

    date_str, time_str = get_french_datetime_strings_sms(lead.appointment_date)

    message = (
        f"RDV confirme\n"
        f"{COMPANY_NAME}\n"
        f"Le {date_str} a {time_str}\n"
        f"{COMPANY_ADDRESS_SHORT}\n"
        f"Tel: {COMPANY_PHONE}\n"
        f"Merci de votre confiance"
    )

    message = normalize_sms(message)
    message = validate_sms_length(message)

    return send_sms(
        message=message,
        receivers=[phone],
    )


# ======================================================
# ⏰ SMS RAPPEL RDV
# ======================================================
def send_appointment_reminder_sms(lead):
    if not lead.phone or not lead.appointment_date:
        return

    phone = normalize_phone(lead.phone)
    if not phone:
        return

    date_str, time_str = get_french_datetime_strings_sms(lead.appointment_date)

    message = (
        f"Rappel RDV\n"
        f"{COMPANY_NAME}\n"
        f"Le {date_str} a {time_str}\n"
        f"{COMPANY_ADDRESS_SHORT}\n"
        f"Tel: {COMPANY_PHONE}"
    )

    message = normalize_sms(message)
    message = validate_sms_length(message)

    return send_sms(
        message=message,
        receivers=[phone],
    )


# ======================================================
# 🛡️ Version ultra-safe (<140 caractères garanti)
# ======================================================
def send_appointment_sms_safe(lead, sms_type="confirmation"):
    if not lead.phone or not lead.appointment_date:
        return

    phone = normalize_phone(lead.phone)
    if not phone:
        return

    date_str, time_str = get_french_datetime_strings_sms(lead.appointment_date)

    if sms_type == "confirmation":
        message = (
            f"RDV confirme le {date_str} {time_str}. "
            f"{COMPANY_NAME}, {COMPANY_ADDRESS_SHORT}. "
            f"Tel: {COMPANY_PHONE}."
        )
    else:
        message = (
            f"Rappel RDV le {date_str} {time_str}. "
            f"{COMPANY_NAME}, {COMPANY_ADDRESS_SHORT}. "
            f"Tel: {COMPANY_PHONE}."
        )

    message = normalize_sms(message)

    return send_sms(
        message=message,
        receivers=[phone],
    )