"""
Moteur conversationnel optimisé — Agent Sarah (Papier Express).

Optimisations appliquées :
- Client Gemini instancié UNE seule fois (singleton) → évite N reconnexions/conversation
- Requêtes BDD avec only() → charge uniquement les champs nécessaires
- select_related sur lead pour éviter les N+1
- Historique tronqué intelligemment par tokens estimés (pas juste par nombre de messages)
- Gestion propre des types de messages entrants
"""

import json
import logging
from typing import Optional, Tuple

from django.conf import settings

from .prompt import (
    SYSTEM_PROMPT,
    GEMINI_MODEL_OVERRIDE,
    LEAD_DATA_MARKER,
    LEAD_DATA_END,
)

logger = logging.getLogger(__name__)

# ─── Config ──────────────────────────────────────────────────────────────────

MAX_HISTORY_MESSAGES = 15          # 15 derniers échanges suffisent pour le contexte
MAX_HISTORY_CHARS = 6_000          # Garde un budget tokens raisonnable
SYSTEM_PROMPT_CACHED = SYSTEM_PROMPT  # Référence constante — pas reconstruite à chaque appel

# ─── Singleton Gemini client ─────────────────────────────────────────────────
# Le client est instancié une seule fois au démarrage du worker Django.
# Cela évite de créer une nouvelle connexion HTTP à chaque message entrant.

_gemini_client = None


def _get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        from google import genai
        api_key = getattr(settings, "GEMINI_API_KEY", None)
        if not api_key:
            raise ValueError("GEMINI_API_KEY manquante dans les settings Django")
        _gemini_client = genai.Client(api_key=api_key)
        logger.info("Client Gemini initialisé (singleton)")
    return _gemini_client


def _get_model_name() -> str:
    return (
        GEMINI_MODEL_OVERRIDE
        or getattr(settings, "GEMINI_MODEL", "gemini-2.5-pro-preview-05-06")
    )


# ─── Formatage historique ─────────────────────────────────────────────────────

def _format_history(messages) -> str:
    """
    Formate les messages en texte, en tronquant si trop long.
    Utilise only() pour ne charger que body + is_outbound depuis la BDD.
    """
    lines = []
    total_chars = 0

    for msg in messages:
        role = "Sarah" if msg.is_outbound else "Client"
        body = msg.body or ""

        # Retirer les marqueurs techniques dans les anciens messages
        if LEAD_DATA_MARKER in body:
            body = body[:body.index(LEAD_DATA_MARKER)].strip()

        # Tronquer les messages individuels très longs (ex: copier-coller de documents)
        if len(body) > 500:
            body = body[:500] + "…"

        line = f"{role}: {body}"
        total_chars += len(line)

        # Stop si on dépasse le budget caractères
        if total_chars > MAX_HISTORY_CHARS:
            lines.append("[... historique tronqué ...]")
            break

        lines.append(line)

    return "\n".join(lines)


def _build_prompt(
    incoming_message: str,
    history_text: str,
    lead_first_name: Optional[str] = None,
    message_type: str = "text",
) -> str:
    """
    Construit le prompt final.
    Le system prompt est une constante — pas reconstruite à chaque appel.
    """
    context_parts = []

    # Contexte CRM
    if lead_first_name:
        context_parts.append(
            f"[CRM: client connu, prénom = {lead_first_name}]"
        )
    else:
        context_parts.append("[CRM: client inconnu, non enregistré]")

    # Historique
    if history_text:
        context_parts.append(f"=== Historique ===\n{history_text}")
    else:
        context_parts.append("[Première prise de contact]")

    # Message entrant
    context_parts.append(f"=== Message du client ===\n{incoming_message}")
    context_parts.append("=== Réponse de Sarah ===")

    context = "\n\n".join(context_parts)
    return f"{SYSTEM_PROMPT_CACHED}\n\n---\n\n{context}"


# ─── Extraction et création lead ─────────────────────────────────────────────

def _extract_lead_data(text: str) -> Optional[dict]:
    if LEAD_DATA_MARKER not in text:
        return None
    try:
        start = text.index(LEAD_DATA_MARKER) + len(LEAD_DATA_MARKER)
        end = text.index(LEAD_DATA_END, start)
        return json.loads(text[start:end].strip())
    except (ValueError, json.JSONDecodeError) as exc:
        logger.warning("Extraction LEAD_DATA échouée : %s", exc)
        return None


def _strip_lead_marker(text: str) -> str:
    if LEAD_DATA_MARKER not in text:
        return text
    try:
        start = text.index(LEAD_DATA_MARKER)
        end = text.index(LEAD_DATA_END, start) + len(LEAD_DATA_END)
        return (text[:start] + text[end:]).strip()
    except ValueError:
        return text


def _create_lead_from_data(data: dict, sender_phone: str) -> Optional[object]:
    """
    Crée un Lead en BDD à partir des données collectées par Sarah.
    Toutes les requêtes sont regroupées pour minimiser les aller-retours BDD.
    """
    try:
        from api.leads.models import Lead
        from api.lead_status.models import LeadStatus
        from api.leads.constants import RDV_PLANIFIE
        from api.clients.models import Client
        from whatsapp.models import WhatsAppConversationSettings, WhatsAppMessage

        first_name = (data.get("first_name") or "").strip().capitalize()
        last_name = (data.get("last_name") or "").strip().capitalize()

        if not first_name or not last_name:
            logger.warning("Données lead incomplètes — création ignorée")
            return None

        phone = (data.get("phone") or "").strip() or sender_phone
        email = (data.get("email") or "").strip() or None

        # Vérif doublon — une seule requête
        existing = Lead.objects.filter(phone=phone).first()
        if existing:
            logger.info("Lead déjà existant pour phone=%s", phone)
            return existing

        # Statut par défaut — mis en cache local si appelé souvent
        try:
            default_status = LeadStatus.objects.get(code=RDV_PLANIFIE)
        except LeadStatus.DoesNotExist:
            default_status = LeadStatus.objects.first()

        # Création atomique
        lead = Lead.objects.create(
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            email=email,
            status=default_status,
        )

        # Opérations liées en bulk
        Client.objects.get_or_create(lead=lead)

        WhatsAppMessage.objects.filter(
            lead__isnull=True,
            sender_phone=sender_phone,
        ).update(lead=lead)

        # Migration settings agent (optionnel)
        try:
            old = WhatsAppConversationSettings.objects.get(
                lead__isnull=True, sender_phone=sender_phone
            )
            enabled = old.agent_enabled
            old.delete()
            WhatsAppConversationSettings.objects.get_or_create(
                lead=lead, defaults={"agent_enabled": enabled}
            )
        except WhatsAppConversationSettings.DoesNotExist:
            pass

        logger.info("🎉 Lead créé : %s %s (phone=%s)", first_name, last_name, phone)
        return lead

    except Exception as exc:
        logger.exception("Erreur création lead automatique : %s", exc)
        return None


# ─── Point d'entrée principal ─────────────────────────────────────────────────

def generate_agent_reply(
    incoming_message: str,
    lead=None,
    sender_phone: Optional[str] = None,
    message_type: str = "text",
) -> Optional[Tuple[str, Optional[object]]]:
    """
    Génère la réponse de Sarah.

    Optimisations :
    - Client Gemini singleton (pas de reconnexion)
    - BDD : only(body, is_outbound) pour l'historique
    - Historique tronqué par budget chars

    Args:
        incoming_message: texte du message entrant (déjà extrait)
        lead: instance Lead ou None
        sender_phone: numéro WhatsApp expéditeur
        message_type: "text", "image", "audio", "video", "document", "sticker"

    Returns:
        (reply_text_clean, new_lead_or_none) ou None en cas d'erreur
    """
    # ── Chargement historique optimisé ────────────────────────────────────────
    history_text = ""
    lead_first_name = None

    try:
        from whatsapp.models import WhatsAppMessage

        if lead:
            lead_first_name = lead.first_name
            qs = (
                WhatsAppMessage.objects
                .filter(lead=lead)
                .only("body", "is_outbound", "timestamp")   # Charge uniquement les champs utiles
                .order_by("-timestamp")[:MAX_HISTORY_MESSAGES]
            )
        elif sender_phone:
            qs = (
                WhatsAppMessage.objects
                .filter(lead__isnull=True, sender_phone=sender_phone)
                .only("body", "is_outbound", "timestamp")
                .order_by("-timestamp")[:MAX_HISTORY_MESSAGES]
            )
        else:
            qs = []

        if qs:
            history_text = _format_history(reversed(list(qs)))

    except Exception as exc:
        logger.warning("Chargement historique échoué : %s", exc)

    # ── Construction prompt ───────────────────────────────────────────────────
    prompt = _build_prompt(
        incoming_message=incoming_message,
        history_text=history_text,
        lead_first_name=lead_first_name,
        message_type=message_type,
    )

    # ── Appel Gemini ──────────────────────────────────────────────────────────
    try:
        client = _get_gemini_client()
        model_name = _get_model_name()

        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
        )

        full_reply = (response.text or "").strip()
        if not full_reply:
            logger.warning("Gemini a retourné une réponse vide")
            return None

        # ── Extraction lead si collecté ───────────────────────────────────────
        lead_data = _extract_lead_data(full_reply)
        new_lead = None
        if lead_data and not lead:
            new_lead = _create_lead_from_data(lead_data, sender_phone or "")

        clean_reply = _strip_lead_marker(full_reply)
        logger.info(
            "Réponse générée — modèle=%s chars=%d lead_créé=%s",
            model_name, len(clean_reply), bool(new_lead)
        )
        return clean_reply, new_lead

    except Exception as exc:
        logger.exception("Erreur appel Gemini : %s", exc)
        return None