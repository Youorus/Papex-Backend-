"""
Handler d'intégration agent IA <-> système WhatsApp.

Optimisations :
- Détection du type de message AVANT l'appel Gemini (médias → réponse directe sans appel IA)
- Vérification agent en une seule requête BDD avec select_related
- Transmission du message_type au moteur pour contexte
"""

import logging
from typing import Optional

from api.whatsapp.models import WhatsAppMessage, WhatsAppConversationSettings
from api.whatsapp.utils import send_whatsapp_message, normalize_phone_for_meta

logger = logging.getLogger(__name__)

# Réponses statiques pour les médias — évite un appel Gemini inutile
# Sarah répond directement, de façon humaine, sans consommer de tokens
MEDIA_RESPONSES = {
    "[Audio]": (
        "Bonjour 😊 Je vois que vous m'avez envoyé un message vocal, "
        "mais je ne peux pas l'écouter depuis cette messagerie. "
        "Pouvez-vous m'écrire votre question ? Je vous réponds tout de suite !"
    ),
    "[Image]": (
        "Bonjour 😊 J'ai reçu votre image mais je ne peux pas l'ouvrir "
        "depuis cette messagerie. "
        "Pouvez-vous m'expliquer votre situation en quelques mots ? Je suis là !"
    ),
    "[Video]": (
        "Bonjour 😊 Je ne peux pas visionner les vidéos depuis ici. "
        "Dites-moi ce dont vous avez besoin par écrit, je vous réponds aussitôt !"
    ),
    "[Document]": (
        "Bonjour 😊 J'ai reçu votre document mais je ne peux pas l'ouvrir "
        "depuis cette messagerie. "
        "Pouvez-vous me décrire votre situation ? Je vous aide directement !"
    ),
    "[Sticker]": (
        "Bonjour 😊 Comment puis-je vous aider aujourd'hui ? "
        "N'hésitez pas à m'écrire votre question !"
    ),
}


def _is_media_message(body: str) -> bool:
    return body.strip() in MEDIA_RESPONSES


def _should_reply(body: str) -> bool:
    if not body or not body.strip():
        return False
    return True


def trigger_agent_response(
    incoming_body: str,
    sender_phone: str,
    lead=None,
) -> Optional[str]:
    """
    Orchestrateur principal.

    Flux optimisé :
    1. Vérification activation globale (settings)
    2. Filtre message vide
    3. Vérification activation par conversation (1 requête BDD)
    4a. Si média → réponse statique directe (0 token Gemini)
    4b. Sinon → appel Gemini
    5. Envoi + sauvegarde
    """
    from django.conf import settings

    if not getattr(settings, "WHATSAPP_AGENT_ENABLED", False):
        return None

    if not _should_reply(incoming_body):
        return None

    # ── Vérification activation par conversation ──────────────────────────────
    try:
        agent_on = WhatsAppConversationSettings.is_agent_enabled(
            lead=lead,
            phone=sender_phone if not lead else None,
        )
        if not agent_on:
            logger.info("Agent en pause — phone=%s", sender_phone)
            return None
    except Exception as exc:
        logger.warning("Vérification settings conversation échouée : %s", exc)

    # ── Réponse directe pour les médias (sans appel Gemini) ───────────────────
    body_stripped = incoming_body.strip()
    if _is_media_message(body_stripped):
        reply_text = MEDIA_RESPONSES[body_stripped]
        logger.info("Réponse média statique — pas d'appel Gemini")
        return _send_and_save(reply_text, sender_phone, lead)

    # ── Appel Gemini pour les messages texte ─────────────────────────────────
    from .engine import generate_agent_reply
    result = generate_agent_reply(
        incoming_message=incoming_body,
        lead=lead,
        sender_phone=sender_phone,
        message_type="text",
    )

    if not result:
        return None

    reply_text, new_lead = result
    effective_lead = new_lead or lead

    return _send_and_save(reply_text, sender_phone, effective_lead)


def _send_and_save(reply_text: str, sender_phone: str, lead=None) -> Optional[str]:
    """Envoie le message via Meta et le sauvegarde en BDD."""
    try:
        to_phone = normalize_phone_for_meta(sender_phone)
        meta_response = send_whatsapp_message(to_phone, reply_text)

        wa_id = (
            meta_response.get("messages", [{}])[0].get("id")
            or f"agent_{to_phone}_{reply_text[:8]}"
        )

        WhatsAppMessage.objects.create(
            wa_id=wa_id,
            lead=lead,
            sender_phone=to_phone,
            body=reply_text,
            is_outbound=True,
            is_read=True,
            delivery_status="sent",
        )

        logger.info(
            "✅ Réponse envoyée — phone=%s lead=%s len=%d",
            sender_phone,
            f"{lead.first_name} {lead.last_name}" if lead else "inconnu",
            len(reply_text),
        )
        return reply_text

    except Exception as exc:
        logger.exception("Erreur envoi réponse agent : %s", exc)
        return None