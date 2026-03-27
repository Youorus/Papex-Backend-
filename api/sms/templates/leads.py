from api.sms.constants import COMPANY_NAME, COMPANY_ADDRESS_SHORT, COMPANY_PHONE, ACCESS_CODE
from api.sms.utils import get_lead_display_name, build_sms
from api.sms.utils_datetime import get_french_datetime_strings_sms

def _name_header(lead) -> str:
    name = get_lead_display_name(lead)
    return f"{name.upper()} : " if name else ""

# ================================================================
# TEMPLATES ACCESSIBLES & SANS AMBIGUITE (1 CREDIT)
# ================================================================

def tpl_appointment_confirmation(lead) -> str:
    d, t = get_french_datetime_strings_sms(lead.appointment_date)
    # "à" et "é" sont autorisés en GSM 7-bit (160 caractères)
    msg = f"{COMPANY_NAME} : {_name_header(lead)}C'est tout bon pour votre RDV le {d} à {t}. On vous attend ! Adresse : {COMPANY_ADDRESS_SHORT}"
    return build_sms(msg)

def tpl_appointment_reminder(lead) -> str:
    d, t = get_french_datetime_strings_sms(lead.appointment_date)
    msg = f"{COMPANY_NAME} : {_name_header(lead)}Petit rappel pour notre RDV de {t}. À très vite ! Adresse : {COMPANY_ADDRESS_SHORT}"
    return build_sms(msg)

def tpl_dossier_status_updated(lead) -> str:
    # On évite "ça" (ç) qui coûte cher, on utilise "tout" ou "votre dossier"
    msg = f"{COMPANY_NAME} : {_name_header(lead)}Bonne nouvelle : tout avance pour votre dossier ! On continue le travail. Tél : {COMPANY_PHONE}"
    return build_sms(msg)

def tpl_absent_urgency(lead) -> str:
    msg = f"{COMPANY_NAME} : {_name_header(lead)}Mince, on vous a manqué ! Tout va bien ? Rappelez-nous au {COMPANY_PHONE} pour faire le point."
    return build_sms(msg)

def tpl_absent_followup(lead, week: int = 1) -> str:
    txt = "on a besoin de vous pour avancer" if week == 1 else "votre dossier est en pause, on s'appelle ?"
    msg = f"{COMPANY_NAME} : {_name_header(lead)}{txt}. Tél : {COMPANY_PHONE}"
    return build_sms(msg)

def tpl_present_no_contract(lead) -> str:
    msg = f"{COMPANY_NAME} : {_name_header(lead)}Merci d'être venu. On fait quoi pour la suite ? On est là pour vous aider. Tél : {COMPANY_PHONE}"
    return build_sms(msg)

def tpl_contract_signed(lead) -> str:
    # "Lancer" au lieu de "Lancé" si on veut être sûr, mais "é" passe très bien
    msg = f"{COMPANY_NAME} : {_name_header(lead)}C'est parti ! Votre dossier est lancé. On s'occupe de toute la paperasse pour vous."
    return build_sms(msg)

def tpl_confirm_presence(lead) -> str:
    d, t = get_french_datetime_strings_sms(lead.appointment_date)
    msg = f"{COMPANY_NAME} : {_name_header(lead)}Vous venez toujours pour le RDV à {t} ? Dites-nous si c'est ok au {COMPANY_PHONE}"
    return build_sms(msg)