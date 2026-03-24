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
    """
    Normalise un numéro de téléphone au format E.164 FR.
    Accepte : 06..., 07..., +336..., +337..., 336..., 337...
    Rejette tout numéro non mobile français.
    Retourne "" si invalide.
    """
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
# 👤 Nom affiché du lead (prénom prioritaire)
# ======================================================

def get_lead_display_name(lead) -> str:
    """
    Retourne le prénom si disponible, sinon le nom.
    Retourne "" si aucun des deux n'est renseigné.
    """
    first = (lead.first_name or "").strip()
    last  = (lead.last_name  or "").strip()
    return first or last or ""


# ======================================================
# 🏷️ Label SMS du service du lead
# ======================================================

def get_service_sms_label(lead) -> str:
    """
    Retourne le libellé SMS normalisé ASCII du service du lead.
    Priorité :
      1. Service du contrat lié (lead.contract_services)
      2. SERVICE_SMS_LABELS[lead.service] (fallback champ direct)
      3. SERVICE_SMS_FALLBACK ("votre dossier")
    """
    # 1. Service via le contrat
    contract_services = lead.contract_services
    if contract_services:
        # On prend le premier contrat actif
        service = contract_services.first()
        if service:
            return SERVICE_SMS_LABELS.get(str(service), SERVICE_SMS_FALLBACK)

    # 2. Fallback sur le champ lead.service direct
    code = lead.service if lead.service else None
    if code:
        return SERVICE_SMS_LABELS.get(code, SERVICE_SMS_FALLBACK)

    # 3. Fallback ultime
    return SERVICE_SMS_FALLBACK


# ======================================================
# ✍️ Normalisation texte GSM 7-bit
# ======================================================

def normalize_sms(text: str) -> str:
    """
    Remplace les caractères non-GSM 7-bit par leurs équivalents ASCII.
    Nécessaire pour garantir le comptage à 160 chars / crédit OVH.
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
# 📏 Validation longueur SMS (1 crédit = 160 chars)
# ======================================================

def validate_sms_length(message: str) -> str:
    """
    Vérifie que le message ne dépasse pas SMS_MAX_LENGTH (160).
    Si trop long, tente deux raccourcissements successifs :
      1. Remplace l'adresse complète par "Paris 17"
      2. Remplace le nom de la société par "Papiers Exp"
    Lève ValueError si toujours trop long après optimisation.
    """
    if len(message) <= SMS_MAX_LENGTH:
        return message

    shortened = message.replace(COMPANY_ADDRESS_SHORT, "Paris 17")

    if len(shortened) > SMS_MAX_LENGTH:
        shortened = shortened.replace(COMPANY_NAME, "Papiers Exp")

    if len(shortened) > SMS_MAX_LENGTH:
        raise ValueError(
            f"SMS trop long apres optimisation ({len(shortened)} caracteres)"
        )

    return shortened