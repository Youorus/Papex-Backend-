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
from ..models import WhatsAppMessage

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
    return GEMINI_MODEL_OVERRIDE or getattr(settings, "GEMINI_MODEL", "gemini-2.5-pro")


def _format_history(messages) -> str:
    lines = []
    total_chars = 0

    for msg in messages:
        role = "Kemora" if msg.is_outbound else "Client"
        body = msg.body or ""

        if LEAD_DATA_MARKER in body:
            body = body[:body.index(LEAD_DATA_MARKER)].strip()

        if len(body) > 400:
            body = body[:400] + "…"

        line = f"{role}: {body}"
        total_chars += len(line)

        if total_chars > MAX_HISTORY_CHARS:
            lines.insert(0, "[historique tronqué — conversation longue]")
            break

        lines.append(line)

    return "\n".join(lines)


def _build_prompt(
    incoming_message: str,
    history_text: str,
    lead_first_name: Optional[str] = None,
    first_contact: bool = True,
) -> str:
    context_parts = []

    if lead_first_name:
        context_parts.append(f"[CRM: client connu, prénom = {lead_first_name}]")
    else:
        context_parts.append("[CRM: client inconnu, non enregistré]")

    if first_contact:
        context_parts.append(
            "[ÉTAT: PREMIER CONTACT — présente-toi brièvement en tant que Kemora "
            "du cabinet Papiers Express, puis demande comment aider.]"
        )
    else:
        context_parts.append(
            "[ÉTAT: CONVERSATION EN COURS — tu t'es déjà présenté. "
            "NE PAS dire Bonjour. NE PAS te représenter. "
            "Réponds directement et naturellement à la suite de la conversation.]"
        )

    if history_text:
        context_parts.append(f"=== Historique ===\n{history_text}")
    else:
        context_parts.append("[Pas d'historique]")

    context_parts.append(f"=== Nouveau message du client ===\n{incoming_message}")
    context_parts.append("=== Réponse de Kemora ===")

    return f"{SYSTEM_PROMPT_CACHED}\n\n---\n\n" + "\n\n".join(context_parts)


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


def _dispatch_lead_creation(data: dict, sender_phone: str) -> None:
    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    phone = (data.get("phone") or "").strip()
    email = (data.get("email") or "").strip() or None
    service_summary = (data.get("service_summary") or "").strip() or None
    appointment_date = (data.get("appointment_date") or "").strip()
    statut_dossier_id = data.get("statut_dossier_id")

    if not first_name or not last_name or not appointment_date:
        logger.info(
            "Lead incomplet — création non déclenchée "
            "(first_name=%s last_name=%s appointment_date=%s)",
            bool(first_name),
            bool(last_name),
            bool(appointment_date),
        )
        return

    try:
        from django_q.tasks import async_task

        async_task(
            "api.whatsapp.agent.lead_service.create_lead_async",
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            email=email,
            service_summary=service_summary,
            sender_phone=sender_phone,
            appointment_date=appointment_date,
            statut_dossier_id=statut_dossier_id,
            q_options={
                "task_name": f"create_lead_{sender_phone}",
                "timeout": 60,
                "max_attempts": 2,
            },
        )

        logger.info(
            "Tâche création lead dispatchée via Django-Q2 — %s %s",
            first_name,
            last_name,
        )

    except ImportError:
        logger.warning("Django-Q2 non disponible — fallback synchrone")
        from .lead_service import create_lead_from_kemora

        create_lead_from_kemora(
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            email=email,
            service_summary=service_summary,
            sender_phone=sender_phone,
            appointment_date=appointment_date,
            statut_dossier_id=statut_dossier_id,
        )

    except Exception as exc:
        logger.exception("Erreur dispatch création lead : %s", exc)


def generate_agent_reply(
    incoming_message: str,
    lead=None,
    sender_phone: Optional[str] = None,
    first_contact: bool = True,
) -> Optional[Tuple[str, None]]:
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
            logger.warning("Gemini — réponse vide")
            return None

        lead_data = _extract_lead_data(full_reply)

        if lead_data and not lead:
            _dispatch_lead_creation(lead_data, sender_phone or "")

        clean_reply = _strip_lead_marker(full_reply)

        logger.info(
            "Kemora — réponse générée | modèle=%s first=%s chars=%d lead_data=%s",
            model_name,
            first_contact,
            len(clean_reply),
            bool(lead_data),
        )

        return clean_reply, None

    except Exception as exc:
        logger.exception("Erreur appel Gemini : %s", exc)
        return None