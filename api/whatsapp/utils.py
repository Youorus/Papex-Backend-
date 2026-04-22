import logging

import requests
from django.conf import settings

from api.leads.models import Lead

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Matching lead ← numéro Meta
# ─────────────────────────────────────────────────────────────

def get_lead_by_phone(wa_phone: str) -> Lead | None:
    """
    Meta envoie généralement un numéro du type '33612345678'.
    On cherche dans Lead.phone sur les 9 derniers chiffres
    pour être plus tolérant au format stocké en base.
    """
    if not wa_phone:
        return None

    clean = wa_phone[-9:]
    return Lead.objects.filter(phone__icontains=clean).first()


# ─────────────────────────────────────────────────────────────
# Normalisation du numéro pour Meta (format E.164 sans +)
# ─────────────────────────────────────────────────────────────

def normalize_phone_for_meta(phone: str) -> str:
    """
    Convertit n'importe quel format en E.164 sans le +.
    Ex:
      '+33 6 12 34 56 78' -> '33612345678'
      '06 12 34 56 78'    -> '33612345678'
      '32487241425'       -> '32487241425'
    """
    cleaned = "".join(c for c in phone if c.isdigit())

    # Cas FR local : 06xxxxxxxx ou 07xxxxxxxx
    if cleaned.startswith("0"):
        cleaned = "33" + cleaned[1:]

    return cleaned


# ─────────────────────────────────────────────────────────────
# Envoi d'un message texte via l'API Meta Cloud
# ─────────────────────────────────────────────────────────────

def send_whatsapp_message(to_phone: str, body: str) -> dict:
    """
    Envoie un message texte via l'API Meta WhatsApp Cloud.

    Settings requis :
      - WHATSAPP_PHONE_NUMBER_ID
      - WHATSAPP_ACCESS_TOKEN

    Retourne le JSON Meta ou lève une exception HTTP.
    """
    phone_number_id = getattr(settings, "WHATSAPP_PHONE_NUMBER_ID", None)
    access_token = getattr(settings, "WHATSAPP_ACCESS_TOKEN", None)

    if not phone_number_id or not access_token:
        raise ValueError("WHATSAPP_PHONE_NUMBER_ID ou WHATSAPP_ACCESS_TOKEN manquant")

    url = f"https://graph.facebook.com/v25.0/{phone_number_id}/messages"

    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {
            "body": body,
        },
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    response = requests.post(url, json=payload, headers=headers, timeout=15)

    if response.status_code not in (200, 201):
        logger.error(
            "Échec envoi WhatsApp | to=%s | status=%s | body=%s",
            to_phone,
            response.status_code,
            response.text,
        )
        response.raise_for_status()

    data = response.json()
    logger.info("Message WhatsApp envoyé | to=%s | response=%s", to_phone, data)
    return data


# ─────────────────────────────────────────────────────────────
# Typing indicator WhatsApp
# ─────────────────────────────────────────────────────────────

def send_whatsapp_typing_indicator(wa_message_id: str) -> dict | None:
    """
    Envoie l'indicateur 'typing...' via WhatsApp Cloud API.

    Important :
      - wa_message_id doit être l'ID du message ENTRANT reçu depuis le webhook
      - l'appel est non bloquant côté métier : si ça échoue, l'agent continue

    Meta utilise l'endpoint /messages avec:
      - status = "read"
      - message_id = <message entrant>
      - typing_indicator = {"type": "text"}
    """
    phone_number_id = getattr(settings, "WHATSAPP_PHONE_NUMBER_ID", None)
    access_token = getattr(settings, "WHATSAPP_ACCESS_TOKEN", None)

    if not phone_number_id or not access_token:
        logger.warning(
            "Typing indicator ignoré | config manquante | phone_number_id=%s | token=%s",
            bool(phone_number_id),
            bool(access_token),
        )
        return None

    if not wa_message_id:
        logger.warning("Typing indicator ignoré | wa_message_id manquant")
        return None

    url = f"https://graph.facebook.com/v25.0/{phone_number_id}/messages"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": wa_message_id,
        "typing_indicator": {
            "type": "text",
        },
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)

        if response.status_code not in (200, 201):
            logger.warning(
                "Typing indicator échoué (non bloquant) | status=%s | body=%s",
                response.status_code,
                response.text,
            )
            return None

        data = response.json()
        logger.info(
            "Typing indicator envoyé | wa_message_id=%s | response=%s",
            wa_message_id,
            data,
        )
        return data

    except Exception as exc:
        logger.warning(
            "Typing indicator exception (non bloquant) | wa_message_id=%s | error=%s",
            wa_message_id,
            exc,
        )
        return None