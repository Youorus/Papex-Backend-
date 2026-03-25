# api/sms/utils.py

import re
import unicodedata

from api.sms.constants import (
    COMPANY_NAME,
    COMPANY_ADDRESS_SHORT,
    SMS_MAX_LENGTH,
    SERVICE_SMS_LABELS,
    SERVICE_SMS_FALLBACK,
)


# ======================================================
# 📞 Normalisation téléphone (OBLIGATOIRE OVH)
# ======================================================

def normalize_phone(phone: str) -> str:
    if not phone:
        return ""

    phone = phone.strip()
    phone = re.sub(r"[^\d+]", "", phone)

    if phone.startswith("0"):
        phone = "+33" + phone[1:]
    elif phone.startswith("33") and not phone.startswith("+"):
        phone = "+" + phone

    if not re.match(r"^\+33[67]\d{8}$", phone):
        return ""

    return phone


# ======================================================
# 👤 Nom affiché du lead
# ======================================================

def get_lead_display_name(lead) -> str:
    first = (lead.first_name or "").strip()
    last  = (lead.last_name  or "").strip()
    return first or last or ""


# ======================================================
# 🧠 SERVICE INTELLIGENT
# ======================================================

def get_lead_service_label_from_contract_or_lead(lead) -> str:
    try:
        contract = (
            lead.form_data.contracts
            .select_related("service")
            .order_by("-created_at")
            .first()
        )
        if contract and contract.service:
            return contract.service.label
    except Exception:
        pass

    try:
        if lead.form_data and lead.form_data.type_demande:
            return lead.form_data.type_demande.label
    except Exception:
        pass

    if lead.service:
        return lead.get_service_display() or lead.service

    return SERVICE_SMS_FALLBACK


# ======================================================
# 🏷️ SERVICE SMS FINAL
# ======================================================

def get_service_sms_label(lead) -> str:
    label = get_lead_service_label_from_contract_or_lead(lead)

    if not label:
        return SERVICE_SMS_FALLBACK

    key = str(label).upper().replace(" ", "_")

    return SERVICE_SMS_LABELS.get(key, label[:40])


# ======================================================
# ✍️ NORMALISATION GSM STRICT (ANTI-UNICODE)
# ======================================================

def normalize_sms(text: str) -> str:
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
        "€": "EUR",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    # 🔥 supprime tous les caractères non GSM (emoji inclus)
    text = text.encode("ascii", "ignore").decode("ascii")

    return text


# ======================================================
# 📏 OPTIMISATION LONGUEUR (SMART)
# ======================================================

def optimize_sms_length(message: str) -> str:
    if len(message) <= SMS_MAX_LENGTH:
        return message

    # 1. raccourcir adresse
    message = message.replace(COMPANY_ADDRESS_SHORT, "Paris 17")

    if len(message) <= SMS_MAX_LENGTH:
        return message

    # 2. raccourcir nom société
    message = message.replace(COMPANY_NAME, "Papiers Exp")

    return message


# ======================================================
# 🔥 GARANTIE 1 SMS (COUPE FINALE)
# ======================================================

def enforce_single_sms(message: str) -> str:
    if len(message) <= SMS_MAX_LENGTH:
        return message

    # coupe propre
    return message[:157] + "..."


# ======================================================
# 🚀 PIPELINE FINAL (UTILISE ÇA)
# ======================================================

def build_sms(message: str) -> str:
    """
    Pipeline complet :
    - GSM safe
    - optimisation longueur
    - garantie 1 crédit
    """

    message = normalize_sms(message)
    message = optimize_sms_length(message)
    message = enforce_single_sms(message)

    return message