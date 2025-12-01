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
    - to_email: email du destinataire
    - subject: sujet
    - template_name: chemin du template HTML Django
    - context: contexte pour le rendu du template
    - attachments: liste de dicts {filename, content, mimetype} (optionnel)
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

    # Ajout des pièces jointes si présentes
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


TDS_FRANCE_ADDRESS = (
    "11 rue de l'Arrivée, 75015 Paris (En face du magasin C&A, dans la galerie)"
)
TDS_FRANCE_PHONE = "06 95 59 70 43"
TDS_FRANCE_CONTACT_EMAIL = "contact@tds-france.fr"
TDS_FRANCE_TEAM_NAME = "TDS France"
TDS_COPYRIGHT = f"© {timezone.now().year} TDS France. Tous droits réservés."


"""
Construit le contexte de base commun à tous les e-mails envoyés par TDS France.
Ce contexte inclut :
- L'utilisateur (lead) concerné
- L'année en cours
- Le copyright TDS France
- Le numéro de téléphone de contact

:param lead: Objet représentant le lead (doit avoir first_name, last_name, etc.)
:return: Dictionnaire de contexte pour le template HTML
"""


def _base_context(lead: object) -> dict:
    year = timezone.now().year
    return {
        "user": lead,
        "year": year,
        "copyright": f"© {year} TDS France. Tous droits réservés.",
        "phone": TDS_FRANCE_PHONE,
    }


def _build_context(
    lead,
    dt=None,
    location=None,
    appointment=None,
    is_jurist=False,
    extra: dict = None,
) -> dict:
    context = _base_context(lead)

    # Si date de rendez-vous présente
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

    # Ajout de contenu spécifique à un email
    if extra:
        context.update(extra)

    return context
