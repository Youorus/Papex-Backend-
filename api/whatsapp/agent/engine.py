"""
Moteur conversationnel — Agent Kemora (Papiers Express).
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
from ..models import WhatsAppMessage, WhatsAppConversationSettings

logger = logging.getLogger(__name__)

MAX_HISTORY_MESSAGES = 15
MAX_HISTORY_CHARS = 6_000
SYSTEM_PROMPT_CACHED = SYSTEM_PROMPT

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
        or getattr(settings, "GEMINI_MODEL", "gemini-2.5-pro")
    )


def _format_history(messages) -> str:
    lines = []
    total_chars = 0
    for msg in messages:
        role = "Kemora" if msg.is_outbound else "Client"
        body = msg.body or ""
        if LEAD_DATA_MARKER in body:
            body = body[:body.index(LEAD_DATA_MARKER)].strip()
        if len(body) > 500:
            body = body[:500] + "…"
        line = f"{role}: {body}"
        total_chars += len(line)
        if total_chars > MAX_HISTORY_CHARS:
            lines.append("[historique tronqué]")
            break
        lines.append(line)
    return "\n".join(lines)


def _build_prompt(
    incoming_message: str,
    history_text: str,
    lead_first_name: Optional[str] = None,
    first_contact: bool = True,
) -> str:
    """
    Construit le prompt avec contexte clair sur l'état de la conversation.
    Le paramètre first_contact est crucial pour éviter les re-présentations.
    """
    context_parts = []

    # Contexte CRM
    if lead_first_name:
        context_parts.append(f"[CRM: client connu, prénom = {lead_first_name}]")
    else:
        context_parts.append("[CRM: client inconnu, non enregistré]")

    # Contexte conversation — LE POINT CLÉ
    if first_contact:
        context_parts.append(
            "[ÉTAT CONVERSATION: PREMIER CONTACT — c'est le tout premier message de cette personne. "
            "Tu dois te présenter brièvement : 'Bonjour, je suis Kemora du cabinet Papiers Express...' "
            "puis demander comment tu peux aider.]"
        )
    else:
        context_parts.append(
            "[ÉTAT CONVERSATION: CONVERSATION EN COURS — tu t'es déjà présenté. "
            "NE PAS dire 'Bonjour', NE PAS te représenter. "
            "Continue la conversation naturellement comme si tu parlais déjà avec cette personne.]"
        )

    # Historique
    if history_text:
        context_parts.append(f"=== Historique de la conversation ===\n{history_text}")
    else:
        context_parts.append("[Pas d'historique]")

    # Message entrant
    context_parts.append(f"=== Nouveau message du client ===\n{incoming_message}")
    context_parts.append("=== Réponse de Kemora (continue naturellement) ===")

    context = "\n\n".join(context_parts)
    return f"{SYSTEM_PROMPT_CACHED}\n\n---\n\n{context}"


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
    try:
        from api.leads.models import Lead
        from api.lead_status.models import LeadStatus
        from api.leads.constants import RDV_PLANIFIE
        from api.clients.models import Client

        first_name = (data.get("first_name") or "").strip().capitalize()
        last_name = (data.get("last_name") or "").strip().capitalize()

        if not first_name or not last_name:
            logger.warning("Données lead incomplètes — création ignorée")
            return None

        phone = (data.get("phone") or "").strip() or sender_phone
        email = (data.get("email") or "").strip() or None

        existing = Lead.objects.filter(phone=phone).first()
        if existing:
            logger.info("Lead déjà existant pour phone=%s", phone)
            return existing

        try:
            default_status = LeadStatus.objects.get(code=RDV_PLANIFIE)
        except LeadStatus.DoesNotExist:
            default_status = LeadStatus.objects.first()

        lead = Lead.objects.create(
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            email=email,
            status=default_status,
        )

        Client.objects.get_or_create(lead=lead)

        WhatsAppMessage.objects.filter(
            lead__isnull=True,
            sender_phone=sender_phone,
        ).update(lead=lead)

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

        logger.info("Lead créé : %s %s (phone=%s)", first_name, last_name, phone)
        return lead

    except Exception as exc:
        logger.exception("Erreur création lead : %s", exc)
        return None


def generate_agent_reply(
    incoming_message: str,
    lead=None,
    sender_phone: Optional[str] = None,
    first_contact: bool = True,
) -> Optional[Tuple[str, Optional[object]]]:
    """
    Génère la réponse de Kemora.

    Args:
        first_contact: True = premier message → Kemora se présente.
                       False = conversation en cours → pas de re-présentation.
    """
    history_text = ""
    lead_first_name = None

    try:
        if lead:
            lead_first_name = lead.first_name
            qs = (
                WhatsAppMessage.objects
                .filter(lead=lead)
                .only("body", "is_outbound", "timestamp")
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

    prompt = _build_prompt(
        incoming_message=incoming_message,
        history_text=history_text,
        lead_first_name=lead_first_name,
        first_contact=first_contact,
    )

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

        lead_data = _extract_lead_data(full_reply)
        new_lead = None
        if lead_data and not lead:
            new_lead = _create_lead_from_data(lead_data, sender_phone or "")

        clean_reply = _strip_lead_marker(full_reply)
        logger.info(
            "Kemora a répondu — modèle=%s first_contact=%s chars=%d",
            model_name, first_contact, len(clean_reply)
        )
        return clean_reply, new_lead

    except Exception as exc:
        logger.exception("Erreur appel Gemini : %s", exc)
        return None