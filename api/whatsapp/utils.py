# api/whatsapp/utils.py
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
    Meta envoie '33612345678'.
    On cherche dans Lead.phone sur les 9 derniers chiffres
    pour être agnostique du préfixe pays.
    """
    if not wa_phone:
        return None
    clean = wa_phone[-9:]
    return Lead.objects.filter(phone__icontains=clean).first()


# ─────────────────────────────────────────────────────────────
# Envoi d'un message via l'API Meta Cloud
# ─────────────────────────────────────────────────────────────

def send_whatsapp_message(to_phone: str, body: str) -> dict:
    """
    Envoie un message texte via l'API Meta WhatsApp Cloud.

    Paramètres settings.py requis :
        WHATSAPP_PHONE_NUMBER_ID  — ID du numéro expéditeur
        WHATSAPP_ACCESS_TOKEN     — Token d'accès permanent Meta

    Retourne le JSON de réponse Meta ou lève une exception.
    """
    phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID
    access_token    = settings.WHATSAPP_ACCESS_TOKEN

    url = f"https://graph.facebook.com/v19.0/{phone_number_id}/messages"

    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": body},
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    response = requests.post(url, json=payload, headers=headers, timeout=10)

    if response.status_code != 200:
        logger.error(
            "Échec envoi WhatsApp → %s : %s",
            to_phone,
            response.text,
        )
        response.raise_for_status()

    logger.info("Message WhatsApp envoyé → %s", to_phone)
    return response.json()


# ─────────────────────────────────────────────────────────────
# Typing indicator — affiche les "•••" pendant que Gemini réfléchit
# ─────────────────────────────────────────────────────────────

def send_typing_indicator(to_phone: str, wa_message_id: str) -> None:
    """
    Affiche l'indicateur "en train d'écrire" (•••) côté client WhatsApp.

    Paramètres :
        to_phone      — numéro E.164 sans + (ex: "33612345678")
        wa_message_id — ID du message REÇU (champ "id" dans le webhook Meta).
                        Meta en a besoin pour identifier la conversation.

    Durée : ~25 secondes max, ou disparaît automatiquement quand
    tu envoies le vrai message. Rien à annuler manuellement.

    Non bloquant : si l'appel échoue, Kemora répond quand même normalement.
    """
    phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID
    access_token    = settings.WHATSAPP_ACCESS_TOKEN

    url = f"https://graph.facebook.com/v19.0/{phone_number_id}/messages"

    payload = {
        "messaging_product": "whatsapp",
        "status": "read",              # Double coche bleue + typing en même temps
        "message_id": wa_message_id,   # ID du message reçu de l'utilisateur
        "typing_indicator": {
            "type": "text",            # Seul type supporté par Meta actuellement
        },
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=5)
        if response.status_code == 200:
            logger.info("Typing indicator envoyé → %s", to_phone)
        else:
            logger.warning(
                "Typing indicator échoué (non bloquant) → %s : %s", to_phone, response.text
            )
    except Exception as exc:
        logger.warning("Typing indicator exception (non bloquant) → %s : %s", to_phone, exc)


# ─────────────────────────────────────────────────────────────
# Normalisation du numéro pour Meta (format E.164 sans +)
# ─────────────────────────────────────────────────────────────

def normalize_phone_for_meta(phone: str) -> str:
    """
    Convertit n'importe quel format en E.164 sans le +.
    Ex: '+33 6 12 34 56 78' → '33612345678'
    """
    cleaned = "".join(c for c in phone if c.isdigit())
    # Si commence par 0, on suppose France → remplace par 33
    if cleaned.startswith("0"):
        cleaned = "33" + cleaned[1:]
    return cleaned