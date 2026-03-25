# api/sms/templates/leads.py

from api.sms.constants import COMPANY_NAME, COMPANY_ADDRESS_SHORT, COMPANY_PHONE, ACCESS_CODE
from api.sms.utils import (
    get_lead_display_name,
    get_service_sms_label,
)
from api.sms.utils_datetime import get_french_datetime_strings_sms


# ----------------------------------------------------------------
# Helpers internes
# ----------------------------------------------------------------

def _name_line(lead) -> str:
    name = get_lead_display_name(lead)
    return f"{name},\n" if name else ""


def _service_line(lead) -> str:
    label = get_service_sms_label(lead)
    return f"Dossier : {label}\n" if label else ""


# ================================================================
# 1. CONFIRMATION RDV
# ================================================================

def tpl_appointment_confirmation(lead) -> str:
    date_str, time_str = get_french_datetime_strings_sms(lead.appointment_date)

    return (
        f"{COMPANY_NAME}\n"
        f"{_name_line(lead)}"
        f"Votre rendez-vous est confirme.\n"
        f"Le {date_str} a {time_str}\n"
        f"Code acces : {ACCESS_CODE}\n"
        f"{COMPANY_ADDRESS_SHORT}"
    )


# ================================================================
# 2. RAPPEL RDV
# ================================================================

def tpl_appointment_reminder(lead) -> str:
    date_str, time_str = get_french_datetime_strings_sms(lead.appointment_date)

    return (
        f"{COMPANY_NAME}\n"
        f"{_name_line(lead)}"
        f"{_service_line(lead)}"
        f"Rappel : votre rendez-vous est demain.\n"
        f"Le {date_str} a {time_str}\n"
        f"{COMPANY_ADDRESS_SHORT}"
    )


# ================================================================
# 3. MISE A JOUR DOSSIER (ULTRA MOTIVANT)
# ================================================================

def tpl_dossier_status_updated(lead) -> str:
    status_label = lead.statut_dossier.label if lead.statut_dossier else "en cours"

    return (
        f"{COMPANY_NAME}\n"
        f"{_name_line(lead)}"
        f"Bonne nouvelle.\n"
        f"Votre dossier progresse positivement.\n"
        f"Statut : {status_label}\n"
        f"Nous continuons les demarches pour vous."
    )


# ================================================================
# 4. ABSENT — URGENCE
# ================================================================

def tpl_absent_urgency(lead) -> str:
    name = get_lead_display_name(lead)
    service = get_service_sms_label(lead)

    name_part = f"{name}, " if name else ""

    return (
        f"{COMPANY_NAME}\n"
        f"{name_part}nous vous attendions aujourd'hui\n"
        f"pour votre dossier {service}.\n"
        f"Contactez-nous rapidement : {COMPANY_PHONE}"
    )


# ================================================================
# 5. ABSENT — RELANCE
# ================================================================

def tpl_absent_followup(lead, week: int = 1) -> str:
    name = get_lead_display_name(lead)
    service = get_service_sms_label(lead)

    name_part = f"{name}, " if name else ""

    if week == 1:
        body = (
            f"votre dossier {service} est en attente.\n"
            f"Nous pouvons le finaliser rapidement.\n"
            f"Appelez-nous : {COMPANY_PHONE}"
        )

    elif week == 2:
        body = (
            f"votre dossier {service} est toujours bloque.\n"
            f"Sans votre retour, il ne peut avancer.\n"
            f"Contactez-nous : {COMPANY_PHONE}"
        )

    else:
        body = (
            f"dernier rappel pour votre dossier {service}.\n"
            f"Sans reponse, il sera classe.\n"
            f"{COMPANY_PHONE}"
        )

    return f"{COMPANY_NAME}\n{name_part}{body}"


# ================================================================
# 6. PRESENT SANS CONTRAT (CONVERSION)
# ================================================================

def tpl_present_no_contract(lead) -> str:
    name = get_lead_display_name(lead)
    service = get_service_sms_label(lead)

    name_part = f"{name}, " if name else ""

    return (
        f"{COMPANY_NAME}\n"
        f"{name_part}merci pour votre visite.\n"
        f"Votre projet {service} est pret a avancer.\n"
        f"Nous restons disponibles pour vous accompagner.\n"
        f"Avis : g.page/papiers-express"
    )


# ================================================================
# 7. CONTRAT SIGNE (FIDELISATION)
# ================================================================

def tpl_contract_signed(lead) -> str:
    name = get_lead_display_name(lead)
    service = get_service_sms_label(lead)

    name_part = f"{name}, " if name else ""

    return (
        f"{COMPANY_NAME}\n"
        f"{name_part}felicitations.\n"
        f"Votre dossier {service} est lance.\n"
        f"Nous suivons chaque etape pour vous.\n"
        f"Vous serez informe regulierement."
    )


# ================================================================
# 8. DEMANDE CONFIRMATION PRESENCE
# ================================================================

def tpl_confirm_presence(lead) -> str:
    date_str, time_str = get_french_datetime_strings_sms(lead.appointment_date)

    return (
        f"{COMPANY_NAME}\n"
        f"{_name_line(lead)}"
        f"{_service_line(lead)}"
        f"Merci de confirmer votre presence\n"
        f"au rendez-vous du {date_str} a {time_str}\n"
        f"en appelant : {COMPANY_PHONE}"
    )