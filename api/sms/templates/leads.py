from api.sms.constants import COMPANY_NAME, COMPANY_ADDRESS_SHORT, COMPANY_PHONE, ACCESS_CODE, COMPANY_PHONE_WA
from api.sms.utils import get_lead_display_name, build_sms
from api.sms.utils_datetime import get_french_datetime_strings_sms


def _name_header(lead) -> str:
    name = get_lead_display_name(lead)
    return f"{name.upper()} : " if name else ""


# ================================================================
# TEMPLATES ACCESSIBLES & SANS AMBIGUITE (1 CREDIT - MAX 160 CHARS)
# ================================================================

def tpl_appointment_confirmation(lead) -> str:
    d, t = get_french_datetime_strings_sms(lead.appointment_date)
    msg = (
        f"{COMPANY_NAME}\n"
        f"{_name_header(lead)}RDV confirmé le {d} à {t} avec notre Juriste sur votre démarche en France.\n"
        f"Lieu : {COMPANY_ADDRESS_SHORT} (Code: {ACCESS_CODE})"
    )
    return build_sms(msg)


def tpl_appointment_reminder(lead) -> str:
    d, t = get_french_datetime_strings_sms(lead.appointment_date)
    msg = (
        f"{COMPANY_NAME}\n"
        f"{_name_header(lead)}Rappel : RDV aujourd'hui à {t} avec notre Juriste sur votre situation en France.\n"
        f"{COMPANY_ADDRESS_SHORT} (Code: {ACCESS_CODE})"
    )
    return build_sms(msg)


def tpl_confirm_presence(lead) -> str:
    d, t = get_french_datetime_strings_sms(lead.appointment_date)
    msg = (
        f"{COMPANY_NAME}\n"
        f"{_name_header(lead)}Maintenez-vous le RDV à {t} avec notre Juriste sur votre démarche en France ?\n"
        f"Confirmez au {COMPANY_PHONE}"
    )
    return build_sms(msg)

def tpl_appointment_reminder_24h(lead) -> str:
    """Modèle de rappel 24h avec CTA WhatsApp."""
    _, t = get_french_datetime_strings_sms(lead.appointment_date)

    msg = (
        f"{COMPANY_NAME}\n"
        f"{_name_header(lead)}RDV DEMAIN a {t}.\n"
        f"Confirmez par WhatsApp pour garder votre place :\n"
        f"{COMPANY_PHONE_WA}"
    )
    return build_sms(msg)

def tpl_appointment_reminder_48h(lead) -> str:
    """Modèle de rappel 48h avec CTA WhatsApp."""
    d, t = get_french_datetime_strings_sms(lead.appointment_date)
    msg = (
        f"{COMPANY_NAME}\n"
        f"{_name_header(lead)}RDV dans 48h {d} a {t}.\n"
        f"Important pour votre dossier.\n"
        f"Ecrivez-nous sur WhatsApp pour confirmer : {COMPANY_PHONE_WA}"
    )
    return build_sms(msg)

def tpl_dossier_status_updated(lead) -> str:
    msg = (
        f"{COMPANY_NAME}\n"
        f"{_name_header(lead)}Excellente nouvelle : votre dossier avance !\n"
        f"Notre Juriste continue le travail sur votre démarche.\n"
        f"Contact : {COMPANY_PHONE}"
    )
    return build_sms(msg)


def tpl_absent_urgency(lead) -> str:
    d, t = get_french_datetime_strings_sms(lead.appointment_date)

    msg = (
        f"{COMPANY_NAME}\n"
        f"{_name_header(lead)}RDV manque le {d} a {t}.\n"
        f"Ne perdez pas cette opportunite.\n"
        f"Appelez: {COMPANY_PHONE}"
    )
    return build_sms(msg)


def tpl_absent_followup(lead, week: int = 1) -> str:
    txt = "on a besoin de vous pour avancer" if week == 1 else "votre dossier est bloqué, appelez-nous"
    msg = (
        f"{COMPANY_NAME}\n"
        f"{_name_header(lead)}Suite à votre absence, {txt}.\n"
        f"Tél : {COMPANY_PHONE}"
    )
    return build_sms(msg)


def tpl_present_no_contract(lead) -> str:
    msg = (
        f"{COMPANY_NAME}\n"
        f"{_name_header(lead)}Merci de votre visite.\n"
        f"Notre Juriste reste à disposition pour lancer votre démarche en France.\n"
        f"Tél : {COMPANY_PHONE}"
    )
    return build_sms(msg)


def tpl_contract_signed(lead) -> str:
    msg = (
        f"{COMPANY_NAME}\n"
        f"{_name_header(lead)}C'est parti ! Votre dossier est lancé.\n"
        f"Notre Juriste s'occupe de votre démarche en France."
    )
    return build_sms(msg)