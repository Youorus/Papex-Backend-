import logging
from django.conf import settings
from .config import send_html_email, _base_context

logger = logging.getLogger(__name__)

def send_ai_escalation_alert(lead, reason, sender_phone):
    """
    Envoie une alerte urgente à Marc et Themenain quand l'IA demande de l'aide
    et désactive l'agent pour cette conversation.
    """
    # 1. Désactiver l'agent pour cette conversation
    try:
        from api.whatsapp.models import WhatsAppConversationSettings
        if lead:
            settings, created = WhatsAppConversationSettings.objects.get_or_create(lead=lead)
        elif sender_phone:
            settings, created = WhatsAppConversationSettings.objects.get_or_create(
                lead__isnull=True, sender_phone=sender_phone
            )
        else:
            settings = None
        
        if settings and settings.agent_enabled:
            settings.agent_enabled = False
            settings.save()
            logger.info(
                "Agent Kemia désactivé pour %s suite à escalade.", 
                f"lead #{lead.id}" if lead else sender_phone
            )
    except Exception as e:
        logger.error("Échec de la désactivation de l'agent Kemia : %s", e)

    # 2. Envoyer l'alerte email
    recipients = [
        "marc.takoumba@papiers-express.fr",
        "themenain.bamba@papiers-express.fr"
    ]
    
    subject = f"🚨 ALERTE KEMIA : Intervention humaine requise ({lead.first_name if lead else sender_phone})"

    # On construit un contexte riche pour l'email
    context = _base_context(lead)
    context.update({
        "reason": reason,
        "sender_phone": sender_phone,
        "lead_name": f"{lead.first_name} {lead.last_name}" if lead else "Inconnu",
        "whatsapp_url": f"https://papex-crm.fr/whatsapp/" # Lien direct vers ton CRM
    })

    
    # Template à créer ensuite
    template_name = "email/internal/ai_escalation.html"
    
    for email in recipients:
        try:
            send_html_email(
                to_email=email,
                subject=subject,
                template_name=template_name,
                context=context
            )
            logger.info(f"Alerte escalade IA envoyée à {email}")
        except Exception as e:
            logger.error(f"Échec envoi alerte escalade à {email}: {e}")
