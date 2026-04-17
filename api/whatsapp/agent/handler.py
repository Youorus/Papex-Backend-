"""
Handler d'intégration agent Kemora <-> système WhatsApp.
"""

import logging
from typing import Optional

from api.whatsapp.models import WhatsAppConversationSettings, WhatsAppMessage
from api.whatsapp.utils import normalize_phone_for_meta, send_whatsapp_message

logger = logging.getLogger(__name__)

# Réponses médias — Kemora, ton humain, sans "Bonjour" répété
MEDIA_RESPONSES_FIRST = {
    "[Audio]": "Bonjour 😊 Je suis Kemora du cabinet Papiers Express. Je vois que vous m'avez envoyé un vocal, mais je n'arrive pas à l'écouter depuis ici en ce moment. Pouvez-vous m'écrire votre question ? Je vous réponds de suite !",
    "[Image]": "Bonjour 😊 Je suis Kemora du cabinet Papiers Express. J'ai reçu votre image mais je ne peux pas l'ouvrir depuis cette messagerie. Décrivez-moi votre situation en quelques mots et je vous aide !",
    "[Video]": "Bonjour 😊 Je suis Kemora du cabinet Papiers Express. La vidéo ne s'affiche pas de mon côté ! Dites-moi ce dont vous avez besoin par écrit et je vous réponds aussitôt.",
    "[Document]": "Bonjour 😊 Je suis Kemora du cabinet Papiers Express. Je ne peux pas ouvrir le fichier depuis cette messagerie. Pouvez-vous m'expliquer votre situation en quelques mots ?",
    "[Sticker]": "Bonjour 😊 Je suis Kemora du cabinet Papiers Express. Comment puis-je vous aider aujourd'hui ?",
}

MEDIA_RESPONSES_ONGOING = {
    "[Audio]": "Je n'arrive pas à écouter les vocaux depuis ici 😅 Pouvez-vous m'écrire votre question ? Je vous réponds de suite !",
    "[Image]": "Je ne peux pas ouvrir les fichiers depuis cette messagerie. Décrivez-moi votre situation en quelques mots et je vous aide !",
    "[Video]": "La vidéo ne s'affiche pas de mon côté ! Dites-moi ce dont vous avez besoin par écrit 😊",
    "[Document]": "Je ne peux pas ouvrir ce document depuis ici. Expliquez-moi votre situation en quelques mots ?",
    "[Sticker]": "😄 Vous avez une question ? Je suis là !",
}


def _is_media_message(body: str) -> bool:
    return body.strip() in MEDIA_RESPONSES_FIRST


def _should_reply(body: str) -> bool:
    return bool(body and body.strip())


def _is_first_contact(lead=None, sender_phone: str = "") -> bool:
    """
    Retourne True si c'est le tout premier message de cette conversation.
    On vérifie s'il existe déjà des messages sortants (réponses de Kemora).
    """
    try:
        if lead:
            return not WhatsAppMessage.objects.filter(lead=lead, is_outbound=True).exists()
        elif sender_phone:
            return not WhatsAppMessage.objects.filter(
                lead__isnull=True, sender_phone=sender_phone, is_outbound=True
            ).exists()
    except Exception:
        pass
    return True  # Par défaut : premier contact


def trigger_agent_response(
    incoming_body: str,
    sender_phone: str,
    lead=None,
) -> Optional[str]:
    from django.conf import settings

    if not getattr(settings, "WHATSAPP_AGENT_ENABLED", False):
        return None

    if not _should_reply(incoming_body):
        return None

    # Vérification activation par conversation
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

    # Détecter premier contact AVANT d'enregistrer le message sortant
    first_contact = _is_first_contact(lead=lead, sender_phone=sender_phone)

    # Réponse directe pour les médias (sans appel Gemini)
    body_stripped = incoming_body.strip()
    if _is_media_message(body_stripped):
        if first_contact:
            reply_text = MEDIA_RESPONSES_FIRST.get(body_stripped, MEDIA_RESPONSES_FIRST["[Document]"])
        else:
            reply_text = MEDIA_RESPONSES_ONGOING.get(body_stripped, MEDIA_RESPONSES_ONGOING["[Document]"])
        logger.info("Réponse média statique (first=%s)", first_contact)
        return _send_and_save(reply_text, sender_phone, lead)

    # Appel Gemini pour messages texte
    from .engine import generate_agent_reply
    result = generate_agent_reply(
        incoming_message=incoming_body,
        lead=lead,
        sender_phone=sender_phone,
        first_contact=first_contact,
    )

    if not result:
        return None

    reply_text, new_lead = result
    effective_lead = new_lead or lead

    return _send_and_save(reply_text, sender_phone, effective_lead)


def _send_and_save(reply_text: str, sender_phone: str, lead=None) -> Optional[str]:
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
            "Kemora a répondu — phone=%s lead=%s len=%d",
            sender_phone,
            f"{lead.first_name} {lead.last_name}" if lead else "inconnu",
            len(reply_text),
        )
        return reply_text

    except Exception as exc:
        logger.exception("Erreur envoi réponse Kemora : %s", exc)
        return None