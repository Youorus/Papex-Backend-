# api/sms/templates/leads.py
#
# Templates SMS — leads
# Chaque fonction retourne une chaîne brute (non normalisée).
# La normalisation GSM et la validation longueur sont faites
# en aval dans notifications/leads.py.
#
# Workflow couvert :
#   1. Confirmation RDV        → tpl_appointment_confirmation
#   2. Rappel RDV              → tpl_appointment_reminder
#   3. Absent — urgence        → tpl_absent_urgency
#   4. Absent — relance hebdo  → tpl_absent_followup
#   5. Présent sans contrat    → tpl_present_no_contract
#   6. Contrat signé           → tpl_contract_signed

from api.sms.constants import COMPANY_NAME, COMPANY_ADDRESS_SHORT, COMPANY_PHONE
from api.sms.utils import (
    get_lead_display_name,
    get_service_sms_label,
)
from api.sms.utils_datetime import get_french_datetime_strings_sms


# ----------------------------------------------------------------
# Helpers internes
# ----------------------------------------------------------------

def _name_line(lead) -> str:
    """Ligne prénom optionnelle avec saut de ligne."""
    name = get_lead_display_name(lead)
    return f"{name}\n" if name else ""


def _service_line(lead) -> str:
    """Ligne service optionnelle avec saut de ligne."""
    label = get_service_sms_label(lead)
    return f"Dossier : {label}\n" if label else ""


# ================================================================
# 1. CONFIRMATION RDV
# ================================================================

def tpl_appointment_confirmation(lead) -> str:
    """
    Envoyé à la création du lead si appointment_date présente
    et statut = RDV_A_CONFIRMER.
    """
    date_str, time_str = get_french_datetime_strings_sms(lead.appointment_date)

    return (
        f"{COMPANY_NAME}\n"
        f"{_name_line(lead)}"
        f"{_service_line(lead)}"
        f"RDV confirme\n"
        f"Le {date_str}\n"
        f"A {time_str}\n"
        f"{COMPANY_ADDRESS_SHORT}"
    )


# ================================================================
# 2. RAPPEL RDV (24h avant)
# ================================================================

def tpl_appointment_reminder(lead) -> str:
    """
    Envoyé 24h avant le RDV — une seule fois.
    """
    date_str, time_str = get_french_datetime_strings_sms(lead.appointment_date)

    return (
        f"{COMPANY_NAME}\n"
        f"{_name_line(lead)}"
        f"{_service_line(lead)}"
        f"Rappel : votre RDV est demain\n"
        f"Le {date_str} a {time_str}\n"
        f"{COMPANY_ADDRESS_SHORT}"
    )


# ================================================================
# 3. ABSENT — URGENCE
# ================================================================

def tpl_absent_urgency(lead) -> str:
    """
    Envoyé le jour J si le lead est absent à son RDV.
    """
    name = get_lead_display_name(lead)
    service = get_service_sms_label(lead)

    name_part = f"{name}, nous" if name else "Nous"

    return (
        f"{COMPANY_NAME}\n"
        f"{name_part} vous attendions aujourd'hui\n"
        f"pour votre dossier {service}.\n"
        f"Rappellez-nous vite : {COMPANY_PHONE}"
    )


# ================================================================
# 4. ABSENT — RELANCE HEBDO
# ================================================================

def tpl_absent_followup(lead, week: int = 1) -> str:
    """
    Relance hebdomadaire pour lead absent.
    """
    name = get_lead_display_name(lead)
    service = get_service_sms_label(lead)

    name_part = f"{name}, " if name else ""

    if week == 1:
        body = (
            f"votre dossier {service}\n"
            f"est toujours en attente.\n"
            f"Contactez-nous : {COMPANY_PHONE}"
        )

    elif week == 2:
        body = (
            f"votre dossier {service}\n"
            f"ne peut pas avancer sans vous.\n"
            f"Appelez-nous : {COMPANY_PHONE}"
        )

    else:
        body = (
            f"dernier rappel pour votre\n"
            f"dossier {service}. Sans reponse,\n"
            f"il sera classe : {COMPANY_PHONE}"
        )

    return f"{COMPANY_NAME}\n{name_part}{body}"


# ================================================================
# 5. PRÉSENT SANS CONTRAT
# ================================================================

def tpl_present_no_contract(lead) -> str:
    """
    Envoyé 2-3h après un RDV sans signature.
    """
    name = get_lead_display_name(lead)
    service = get_service_sms_label(lead)

    name_part = f"{name}, merci" if name else "Merci"

    return (
        f"{COMPANY_NAME}\n"
        f"{name_part} pour votre visite.\n"
        f"Votre projet {service}\n"
        f"nous tient a coeur.\n"
        f"Votre avis : g.page/papiers-express"
    )


# ================================================================
# 6. CONTRAT SIGNÉ
# ================================================================

def tpl_contract_signed(lead) -> str:
    """
    Envoyé après signature du contrat.
    """
    name = get_lead_display_name(lead)
    service = get_service_sms_label(lead)

    name_part = f"{name}, felicitations" if name else "Felicitations"

    return (
        f"{COMPANY_NAME}\n"
        f"{name_part} !\n"
        f"Votre dossier {service}\n"
        f"est entre nos mains.\n"
        f"Nous vous informons de chaque etape."
    )

# ================================================================
# 7. DEMANDE CONFIRMATION PRESENCE
# ================================================================

def tpl_confirm_presence(lead) -> str:
    """
    Envoyé 2h après la création du RDV
    pour demander la confirmation de présence.
    """

    date_str, time_str = get_french_datetime_strings_sms(lead.appointment_date)

    return (
        f"{COMPANY_NAME}\n"
        f"{_name_line(lead)}"
        f"{_service_line(lead)}"
        f"Merci de confirmer votre presence\n"
        f"au RDV du {date_str} a {time_str}\n"
        f"en nous appelant au : {COMPANY_PHONE}"
    )