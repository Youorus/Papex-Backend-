"""
Moteur conversationnel — Agent Kemora (Papiers Express).

Multi-conversations : chaque appel est stateless.
Singleton Gemini client pour réutiliser la connexion HTTP.
Création lead déléguée à Django-Q2 (non-bloquant).
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
from ..models import WhatsAppMessage

logger = logging.getLogger(__name__)

MAX_HISTORY_MESSAGES = 15
MAX_HISTORY_CHARS    = 6_000
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


# ─── Historique ───────────────────────────────────────────────────────────────

def _format_history(messages) -> str:
    lines = []
    total_chars = 0
    for msg in messages:
        role = "Kemora" if msg.is_outbound else "Client"
        body = msg.body or ""
        # Retirer les blocs LEAD_DATA de l'historique (jamais visibles dans le contexte)
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


# ─── Prompt ───────────────────────────────────────────────────────────────────

def _build_prompt(
    incoming_message: str,
    history_text: str,
    lead_first_name: Optional[str] = None,
    sender_phone: Optional[str] = None,
    first_contact: bool = True,
) -> str:
    parts = []

    if lead_first_name:
        parts.append(f"[CRM: client connu, prénom = {lead_first_name}]")
    else:
        parts.append("[CRM: client inconnu, non enregistré]")

    # Injecter sender_phone pour que Kemora puisse le mentionner lors de la confirmation
    if sender_phone:
        parts.append(f"[SENDER_PHONE: {sender_phone} — c'est le numéro WhatsApp de la personne. "
                     f"Quand tu demandes la confirmation du téléphone, mentionne ce numéro explicitement.]")

    if first_contact:
        parts.append(
            "[ÉTAT: PREMIER CONTACT — présente-toi brièvement en tant que Kemora "
            "du cabinet Papiers Express, puis demande comment aider.]"
        )
    else:
        parts.append(
            "[ÉTAT: CONVERSATION EN COURS — tu t'es déjà présenté. "
            "NE PAS dire Bonjour. NE PAS te représenter. "
            "Continue directement et naturellement.]"
        )

    parts.append(f"=== Historique ===\n{history_text}" if history_text else "[Pas d'historique]")
    parts.append(f"=== Nouveau message du client ===\n{incoming_message}")
    parts.append("=== Réponse de Kemora ===")

    return f"{SYSTEM_PROMPT_CACHED}\n\n---\n\n" + "\n\n".join(parts)


# ─── Extraction lead data ─────────────────────────────────────────────────────

def _extract_lead_data(text: str) -> Optional[dict]:
    if LEAD_DATA_MARKER not in text:
        return None
    try:
        start = text.index(LEAD_DATA_MARKER) + len(LEAD_DATA_MARKER)
        end   = text.index(LEAD_DATA_END, start)
        return json.loads(text[start:end].strip())
    except (ValueError, json.JSONDecodeError) as exc:
        logger.warning("Extraction LEAD_DATA échouée : %s", exc)
        return None


def _strip_lead_marker(text: str) -> str:
    if LEAD_DATA_MARKER not in text:
        return text
    try:
        start = text.index(LEAD_DATA_MARKER)
        end   = text.index(LEAD_DATA_END, start) + len(LEAD_DATA_END)
        return (text[:start] + text[end:]).strip()
    except ValueError:
        return text


# ─── Validation lead data ─────────────────────────────────────────────────────

def _validate_lead_data(data: dict, sender_phone: str) -> Optional[str]:
    """
    Valide les champs du bloc LEAD_DATA.
    Retourne un message d'erreur si invalide, None si tout est OK.
    """
    first_name = (data.get("first_name") or "").strip()
    last_name  = (data.get("last_name") or "").strip()
    phone      = (data.get("phone") or "").strip()
    appointment_date = (data.get("appointment_date") or "").strip()

    if not first_name:
        return "first_name manquant"
    if not last_name:
        return "last_name manquant"
    if not appointment_date:
        return "appointment_date manquante"

    # Le phone peut être vide si Kemora n'a pas encore la confirmation
    # On fait confiance à sender_phone comme fallback ultime dans lead_service
    # mais on log un avertissement
    if not phone:
        logger.warning(
            "LEAD_DATA sans phone explicite — sender_phone=%s sera utilisé comme fallback",
            sender_phone,
        )

    return None


# ─── Dispatch création lead (async Django-Q2) ─────────────────────────────────

def _dispatch_lead_creation(data: dict, sender_phone: str) -> None:
    """
    Extrait et valide les champs, puis délègue à Django-Q2.

    Champs obligatoires bloquants : first_name, last_name, appointment_date.
    Le phone utilise sender_phone comme fallback si absent du bloc LEAD_DATA
    (cas où Kemora a utilisé le numéro WhatsApp sans le réécrire explicitement).
    """
    first_name        = (data.get("first_name") or "").strip()
    last_name         = (data.get("last_name") or "").strip()
    # Fallback sur sender_phone si phone non fourni ou vide dans le bloc
    phone             = (data.get("phone") or "").strip() or sender_phone
    email             = (data.get("email") or "").strip() or None
    service_summary   = (data.get("service_summary") or "").strip() or None
    appointment_date  = (data.get("appointment_date") or "").strip()
    statut_dossier_id = data.get("statut_dossier_id")

    # ── Validations bloquantes ────────────────────────────────────────────────
    validation_error = _validate_lead_data(data, sender_phone)
    if validation_error:
        logger.warning("Dispatch lead ignoré — %s | data=%s", validation_error, data)
        return

    if not phone:
        logger.warning(
            "Dispatch lead ignoré — phone manquant (ni dans LEAD_DATA ni sender_phone) | data=%s",
            data,
        )
        return

    logger.info(
        "Dispatch lead — %s %s | phone=%s | rdv=%s | email=%s",
        first_name, last_name, phone, appointment_date, email or "—",
    )

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
                "task_name": f"kemora_lead_{sender_phone}",
                "timeout": 60,
                "max_attempts": 2,
            },
        )
        logger.info(
            "Lead dispatché via Django-Q2 — %s %s rdv=%s",
            first_name, last_name, appointment_date,
        )

    except ImportError:
        logger.warning("Django-Q2 indisponible — fallback synchrone")
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
        logger.exception("Erreur dispatch lead : %s", exc)


# ─── Point d'entrée principal ─────────────────────────────────────────────────

def generate_agent_reply(
    incoming_message: str,
    lead=None,
    sender_phone: Optional[str] = None,
    first_contact: bool = True,
) -> Optional[Tuple[str, None]]:
    """
    Génère la réponse de Kemora pour une conversation donnée.
    Chaque appel est totalement indépendant (stateless).
    Retourne (reply_text, None) — la création lead est asynchrone.
    """
    history_text    = ""
    lead_first_name = None

    # ── Historique BDD ────────────────────────────────────────────────────────
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

    # ── Appel Gemini ──────────────────────────────────────────────────────────
    try:
        prompt = _build_prompt(
            incoming_message=incoming_message,
            history_text=history_text,
            lead_first_name=lead_first_name,
            sender_phone=sender_phone,
            first_contact=first_contact,
        )
        client = _get_gemini_client()

        response = client.models.generate_content(
            model=_get_model_name(),
            contents=prompt,
        )

        full_reply = (response.text or "").strip()
        if not full_reply:
            logger.warning("Gemini — réponse vide")
            return None

        # ── Extraction + dispatch lead ────────────────────────────────────────
        lead_data = _extract_lead_data(full_reply)
        if lead_data:
            if not lead:
                # Nouveau client → création complète
                _dispatch_lead_creation(lead_data, sender_phone or "")
            else:
                # Client connu → mise à jour du RDV si appointment_date présente
                appointment_date = (lead_data.get("appointment_date") or "").strip()
                if appointment_date:
                    _dispatch_lead_creation(lead_data, sender_phone or "")
                    logger.info(
                        "Lead connu #%d — mise à jour RDV dispatché : %s",
                        lead.pk, appointment_date,
                    )

        clean_reply = _strip_lead_marker(full_reply)

        logger.info(
            "Kemora — réponse | modèle=%s first=%s chars=%d lead_dispatched=%s",
            _get_model_name(), first_contact, len(clean_reply), bool(lead_data),
        )
        return clean_reply, None

    except Exception as exc:
        logger.exception("Erreur appel Gemini : %s", exc)
        return None