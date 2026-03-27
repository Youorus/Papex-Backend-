# api/sms/templates/leads.py

import random

from api.sms.constants import COMPANY_NAME, COMPANY_ADDRESS_SHORT, COMPANY_PHONE, ACCESS_CODE
from api.sms.utils import get_lead_display_name
from api.sms.utils_datetime import get_french_datetime_strings_sms


# ----------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------

def _name_line(lead) -> str:
    name = get_lead_display_name(lead)
    return f"{name},\n" if name else ""


def _progress_message() -> str:
    """
    🔥 Messages motivants (variation humaine)
    """
    return random.choice([
        "Bonne nouvelle : votre dossier avance bien.",
        "Votre dossier progresse positivement.",
        "Nous avançons activement sur votre dossier.",
        "Votre dossier suit une évolution favorable.",
    ])


# ================================================================
# 1. CONFIRMATION RDV
# ================================================================

def tpl_appointment_confirmation(lead) -> str:
    date_str, time_str = get_french_datetime_strings_sms(lead.appointment_date)

    return (
        f"{COMPANY_NAME}\n"
        f"{_name_line(lead)}"
        f"Votre rendez-vous est bien confirmé.\n"
        f"{date_str} à {time_str}\n"
        f"Code accès : {ACCESS_CODE}\n"
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
        f"Rappel : votre rendez-vous approche.\n"
        f"{date_str} à {time_str}\n"
        f"Nous sommes prêts à vous accompagner.\n"
        f"{COMPANY_ADDRESS_SHORT}"
    )


# ================================================================
# 3. STATUT DOSSIER (🔥 MOTIVANT GLOBAL)
# ================================================================

def tpl_dossier_status_updated(lead) -> str:
    return (
        f"{COMPANY_NAME}\n"
        f"{_name_line(lead)}"
        f"{_progress_message()}\n"
        f"Notre équipe reste mobilisée pour vous.\n"
        f"Besoin d’un point ? {COMPANY_PHONE}"
    )


# ================================================================
# 4. ABSENT — URGENCE
# ================================================================

def tpl_absent_urgency(lead) -> str:
    name = get_lead_display_name(lead)
    name_part = f"{name}, " if name else ""

    return (
        f"{COMPANY_NAME}\n"
        f"{name_part}nous vous attendions aujourd’hui.\n"
        f"Votre situation peut être traitée rapidement.\n"
        f"Contactez-nous sans attendre : {COMPANY_PHONE}"
    )


# ================================================================
# 5. ABSENT — RELANCE
# ================================================================

def tpl_absent_followup(lead, week: int = 1) -> str:
    name = get_lead_display_name(lead)
    name_part = f"{name}, " if name else ""

    if week == 1:
        body = (
            "votre dossier avance mais reste en attente.\n"
            f"Nous pouvons accélérer les choses.\n"
            f"{COMPANY_PHONE}"
        )

    elif week == 2:
        body = (
            "votre dossier peut encore progresser.\n"
            "Une action de votre part peut tout débloquer.\n"
            f"{COMPANY_PHONE}"
        )

    else:
        body = (
            "nous avons fait le maximum pour vous.\n"
            "Contactez-nous pour finaliser votre dossier.\n"
            f"{COMPANY_PHONE}"
        )

    return f"{COMPANY_NAME}\n{name_part}{body}"


# ================================================================
# 6. PRESENT SANS CONTRAT
# ================================================================

def tpl_present_no_contract(lead) -> str:
    name = get_lead_display_name(lead)
    name_part = f"{name}, " if name else ""

    return (
        f"{COMPANY_NAME}\n"
        f"{name_part}merci pour votre venue.\n"
        f"Votre projet est prêt à avancer.\n"
        f"Nous restons à vos côtés pour la suite.\n"
        f"Avis : g.page/papiers-express"
    )


# ================================================================
# 7. CONTRAT SIGNE
# ================================================================

def tpl_contract_signed(lead) -> str:
    name = get_lead_display_name(lead)
    name_part = f"{name}, " if name else ""

    return (
        f"{COMPANY_NAME}\n"
        f"{name_part}félicitations.\n"
        f"Votre dossier est lancé.\n"
        f"Nous suivons chaque étape avec attention.\n"
        f"Vous serez informé régulièrement."
    )


# ================================================================
# 8. CONFIRMATION PRESENCE
# ================================================================

def tpl_confirm_presence(lead) -> str:
    date_str, time_str = get_french_datetime_strings_sms(lead.appointment_date)

    return (
        f"{COMPANY_NAME}\n"
        f"{_name_line(lead)}"
        f"Merci de confirmer votre présence\n"
        f"au rendez-vous du {date_str} à {time_str}\n"
        f"en appelant : {COMPANY_PHONE}"
    )