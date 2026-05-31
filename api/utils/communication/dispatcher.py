import logging
from typing import Optional, Dict, Any
from django.conf import settings
from api.sms.sender import send_sms
from api.sms.utils import build_sms, normalize_phone
from api.utils.email.config import send_html_email, _base_context
from api.leads_events.models import LeadEvent

logger = logging.getLogger(__name__)

class CommunicationDispatcher:
    """
    Moteur unifié pour l'envoi de communications (Email, SMS, WhatsApp).
    Centralise la logique de "double envoi" et l'optimisation des canaux.
    """

    @staticmethod
    def send_notification(
        lead,
        subject: str,
        template_prefix: str,
        context: Dict[str, Any],
        sms_body: Optional[str] = None,
        force_both: bool = False,
    ):
        """
        Envoie une notification via Email et/ou SMS selon la disponibilité des données.
        """
        email_sent = False
        sms_sent = False

        # 1. Tentative EMAIL
        if lead.email:
            try:
                template_name = f"email/{template_prefix}.html"
                email_context = _base_context(lead)
                email_context.update(context)
                
                send_html_email(
                    to_email=lead.email,
                    subject=subject,
                    template_name=template_name,
                    context=email_context
                )
                email_sent = True
                logger.info(f"📧 Notification Email envoyée à {lead.email} (prefix: {template_prefix})")

                # Log LeadEvent
                LeadEvent.log(
                    lead=lead,
                    event_code="EMAIL_SENT",
                    actor=None,
                    data={
                        "subject": subject,
                        "template": template_prefix,
                        "email": lead.email,
                    },
                )
            except Exception as e:
                logger.error(f"❌ Erreur envoi Email ({template_prefix}) pour lead #{lead.id}: {e}")

        # 2. Tentative SMS (si force_both ou si l'email a échoué/est absent)
        should_send_sms = force_both or not email_sent
        
        if should_send_sms and lead.phone and sms_body:
            try:
                clean_phone = normalize_phone(lead.phone)
                if clean_phone:
                    final_sms = build_sms(sms_body)
                    send_sms(
                        message=final_sms,
                        receivers=[clean_phone]
                    )
                    sms_sent = True
                    logger.info(f"📲 Notification SMS envoyée à {clean_phone}")

                    # Log LeadEvent
                    LeadEvent.log(
                        lead=lead,
                        event_code="SMS_SENT",
                        actor=None,
                        data={
                            "template": template_prefix,
                            "phone": clean_phone,
                            "body_preview": (
                                final_sms[:50] + "..."
                                if len(final_sms) > 50
                                else final_sms
                            ),
                        },
                    )
                else:
                    logger.warning(f"⚠️ Numéro de téléphone invalide pour lead #{lead.id}: {lead.phone}")
            except Exception as e:
                logger.error(f"❌ Erreur envoi SMS ({template_prefix}) pour lead #{lead.id}: {e}")

        return email_sent, sms_sent
