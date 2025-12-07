import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from api.utils.email.utils import _get_with_info, get_french_datetime_strings

logger = logging.getLogger(__name__)


def send_html_email(to_email, subject, template_name, context, attachments=None):
    """
    Envoie un email HTML à l'adresse fournie.
    """
    if not to_email:
        logger.warning("Aucun email fourni.")
        return

    html_content = render_to_string(template_name, context)

    msg = EmailMultiAlternatives(
        subject=subject,
        body="",
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to_email],
    )
    msg.attach_alternative(html_content, "text/html")

    # Pièces jointes (optionnel)
    if attachments:
        for att in attachments:
            filename = att.get("filename")
            filecontent = att.get("content")
            mimetype = att.get("mimetype") or "application/pdf"
            if filename and filecontent:
                msg.attach(filename, filecontent, mimetype)
            else:
                logger.warning(f"Attachment ignoré (format incorrect): {att}")

    msg.send()


# ================================
# Branding : Papiers Express
# ================================

COMPANY_NAME = "Papiers-Express"
COMPANY_LEGAL_FORM = "Société par Actions Simplifiée"
COMPANY_RCS = "R.C.S Paris 990 924 201"
COMPANY_ADDRESS = "39 rue Navier, 75017 Paris"
COMPANY_CONTACT = "contact@papiers-express.fr | www.papiers-express.fr"
COMPANY_PHONE = "07 56 98 11 34 / 01 42 59 60 08"
COMPANY_DOOR_CODE = "36B59"

# Assets
LOGO_URL = "https://papiers-express.fr/logo.png"
SIGNATURE_URL = "https://papiers-express.fr/signature.png"

COMPANY_COPYRIGHT = f"© {timezone.now().year} {COMPANY_NAME}. Tous droits réservés."


# ================================
# Contexte base email
# ================================

def _base_context(lead: object) -> dict:
    """
    Construit le contexte commun à tous les emails.
    """
    year = timezone.now().year

    company_data = {
        "name": COMPANY_NAME,
        "legal_form": COMPANY_LEGAL_FORM,
        "rcs": COMPANY_RCS,
        "address": COMPANY_ADDRESS,
        "contact": COMPANY_CONTACT,
        "phone": COMPANY_PHONE,
        "door_code": COMPANY_DOOR_CODE,
        "logo_url": LOGO_URL,
        "signature": SIGNATURE_URL,
        "copyright": f"© {year} {COMPANY_NAME}. Tous droits réservés.",
    }

    return {
        # Utilisateur
        "user": lead,
        "year": year,

        # Objet entreprise (recommandé)
        "company": company_data,

        # Accès direct (compatibilité ascendante)
        "phone": COMPANY_PHONE,
        "company_name": COMPANY_NAME,
        "address": COMPANY_ADDRESS,
        "contact": COMPANY_CONTACT,
        "door_code": COMPANY_DOOR_CODE,

        # Footer
        "copyright": company_data["copyright"],
    }


# ================================
# Contexte spécifique (RDV)
# ================================

def _build_context(
    lead,
    dt=None,
    location=None,
    appointment=None,
    is_jurist=False,
    extra: dict = None,
) -> dict:
    """
    Construit un contexte complet incluant :
    - Données utilisateur
    - Informations rendez-vous
    - Données entreprise
    """
    context = _base_context(lead)

    # RDV si fourni
    if dt:
        date_str, time_str = get_french_datetime_strings(dt)
        with_label, with_name = (
            _get_with_info(appointment) if appointment else (None, None)
        )

        context["appointment"] = {
            "date": date_str,
            "time": time_str,
            "location": location,
            "note": getattr(appointment, "note", "") if appointment else "",
            "with_label": with_label or ("Juriste" if is_jurist else "Conseiller"),
            "with_name": with_name or "",
        }

    # Données spécifiques à l'email
    if extra:
        context.update(extra)

    return context
