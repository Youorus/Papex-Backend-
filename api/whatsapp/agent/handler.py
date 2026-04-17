"""
Handler Kemora — Papiers Express
Gère les conversations parallèles, détecte le premier contact,
traite les médias sans appel Gemini.
"""

import logging
from typing import Optional

from api.whatsapp.models import WhatsAppMessage, WhatsAppConversationSettings
from api.whatsapp.utils import normalize_phone_for_meta, send_whatsapp_message

logger = logging.getLogger(__name__)

MEDIA_FIRST = {
    "[Audio]":    "Bonjour 😊 Je suis Kemora du cabinet Papiers Express. Je n'arrive pas à écouter les vocaux depuis ici. Pouvez-vous m'écrire votre question ? Je vous réponds de suite !",
    "[Image]":    "Bonjour 😊 Je suis Kemora du cabinet Papiers Express. Je ne peux pas ouvrir les images depuis cette messagerie. Décrivez-moi votre situation en quelques mots et je vous aide !",
    "[Video]":    "Bonjour 😊 Je suis Kemora du cabinet Papiers Express. La vidéo ne s'affiche pas de mon côté. Dites-moi ce dont vous avez besoin par écrit !",
    "[Document]": "Bonjour 😊 Je suis Kemora du cabinet Papiers Express. Je ne peux pas ouvrir ce document depuis ici. Expliquez-moi votre situation en quelques mots ?",
    "[Sticker]":  "Bonjour 😊 Je suis Kemora du cabinet Papiers Express. Comment puis-je vous aider aujourd'hui ?",
}

MEDIA_ONGOING = {
    "[Audio]":    "Je n'arrive pas à écouter les vocaux depuis ici 😅 Pouvez-vous m'écrire votre question ?",
    "[Image]":    "Je ne peux pas ouvrir les images depuis cette messagerie. Décrivez-moi votre situation ?",
    "[Video]":    "La vidéo ne s'affiche pas de mon côté ! Dites-moi ce dont vous avez besoin par écrit 😊",
    "[Document]": "Je ne peux pas ouvrir ce document depuis ici. Expliquez-moi votre situation ?",
    "[Sticker]":  "😄 Une question ? Je suis là !",
}

MEDIA_KEYS = set(MEDIA_FIRST.keys())


def _is_media(body: str) -> bool:
    return body.strip() in MEDIA_KEYS


def _should_reply(body: str) -> bool:
    return bool(body and body.strip())


def _is_first_contact(lead=None, sender_phone: str = "") -> bool:
    """Une requête BDD ciblée — index sur sender_phone + is_outbound."""
    try:
        if lead:
            return not WhatsAppMessage.objects.filter(lead=lead, is_outbound=True).exists()
        elif sender_phone:
            return not WhatsAppMessage.objects.filter(
                lead__isnull=True, sender_phone=sender_phone, is_outbound=True
            ).exists()
    except Exception as exc:
        logger.warning("Vérification premier contact échouée : %s", exc)
    return True


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
        if not WhatsAppConversationSettings.is_agent_enabled(
            lead=lead,
            phone=sender_phone if not lead else None,
        ):
            logger.info("Agent en pause — phone=%s", sender_phone)
            return None
    except Exception as exc:
        logger.warning("Vérif settings agent échouée : %s", exc)

    # Détection premier contact AVANT d'enregistrer le message sortant
    first_contact = _is_first_contact(lead=lead, sender_phone=sender_phone)

    # Médias → réponse statique immédiate (0 token Gemini)
    body_stripped = incoming_body.strip()
    if _is_media(body_stripped):
        media_dict = MEDIA_FIRST if first_contact else MEDIA_ONGOING
        reply = media_dict.get(body_stripped, media_dict["[Document]"])
        logger.info("Réponse média statique (first=%s) — phone=%s", first_contact, sender_phone)
        return _send_and_save(reply, sender_phone, lead)

    # Texte → Gemini
    from .engine import generate_agent_reply
    result = generate_agent_reply(
        incoming_message=incoming_body,
        lead=lead,
        sender_phone=sender_phone,
        first_contact=first_contact,
    )

    if not result:
        return None

    reply_text, _ = result
    return _send_and_save(reply_text, sender_phone, lead)


def _send_and_save(reply_text: str, sender_phone: str, lead=None) -> Optional[str]:
    try:
        to_phone     = normalize_phone_for_meta(sender_phone)
        meta_resp    = send_whatsapp_message(to_phone, reply_text)
        wa_id        = (
            meta_resp.get("messages", [{}])[0].get("id")
            or f"kemora_{to_phone}_{reply_text[:6]}"
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
            "Kemora envoyé — phone=%s lead=%s len=%d",
            sender_phone,
            f"{lead.first_name} {lead.last_name}" if lead else "inconnu",
            len(reply_text),
        )
        return reply_text

    except Exception as exc:
        logger.exception("Erreur envoi réponse Kemora : %s", exc)
        return None