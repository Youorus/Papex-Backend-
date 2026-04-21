"""
Moteur conversationnel — Agent Kemora (Papiers Express).

Multi-conversations : chaque appel est stateless.
Singleton Gemini client pour réutiliser la connexion HTTP.

Stratégie de création de lead :
  1. L'engine appelle create_lead_from_kemora() de façon SYNCHRONE par défaut.
     → On obtient immédiatement le résultat (created / updated / error).
     → Si Django-Q2 est disponible ET configuré, on délègue en async.
  2. Si la création réussit, on injecte un contexte [[LEAD_RESULT:...]] dans
     la réponse nettoyée pour que l'engine puisse confirmer à Kemora
     côté message visible (ou pour debug/logging).

Note : La confirmation visible au client est déjà écrite par Kemora
dans son message (section 8 du prompt). On ne la regénère pas.
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


# ─── Client Gemini (singleton) ────────────────────────────────────────────────

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
    from django.utils import timezone as tz
    import locale
    parts = []

    # Date actuelle injectée pour que Kemora puisse résoudre "demain", "après-demain", etc.
    now = tz.localtime(tz.now())
    jours = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    mois  = ["janvier", "février", "mars", "avril", "mai", "juin",
              "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    date_str = f"{jours[now.weekday()]} {now.day} {mois[now.month - 1]} {now.year}"
    parts.append(f"[DATE_ACTUELLE: {date_str} — utilise cette date pour calculer 'demain', 'après-demain', etc. et toujours demander confirmation]")

    if lead_first_name:
        parts.append(f"[CRM: client connu, prénom = {lead_first_name}]")
    else:
        parts.append("[CRM: client inconnu, non enregistré]")

    if sender_phone:
        parts.append(
            f"[SENDER_PHONE: {sender_phone} — c'est le numéro WhatsApp de la personne. "
            f"Quand tu demandes la confirmation du téléphone, mentionne ce numéro explicitement.]"
        )

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


# ─── Extraction / nettoyage LEAD_DATA ─────────────────────────────────────────

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
    first_name       = (data.get("first_name") or "").strip()
    last_name        = (data.get("last_name") or "").strip()
    appointment_date = (data.get("appointment_date") or "").strip()
    phone            = (data.get("phone") or "").strip()

    if not first_name:
        return "first_name manquant"
    if not last_name:
        return "last_name manquant"
    if not appointment_date:
        return "appointment_date manquante"
    if not phone:
        logger.warning(
            "LEAD_DATA sans phone explicite — sender_phone=%s sera utilisé comme fallback",
            sender_phone,
        )
    return None


# ─── Dispatch création lead ───────────────────────────────────────────────────

def _dispatch_lead_creation(data: dict, sender_phone: str) -> dict:
    """
    Crée ou met à jour le lead.

    Stratégie :
    - Tente d'abord Django-Q2 (async) si disponible.
    - Si Django-Q2 indisponible → fallback synchrone immédiat.
    - Retourne le résultat de la création (dict avec status/lead_id/etc.)
      en mode synchrone, ou {"status": "queued"} en mode async.

    Important : en mode async, la confirmation visible au client
    est déjà incluse dans le message Kemora (généré par le LLM).
    En mode sync, on peut vérifier le résultat mais la réponse est
    déjà construite — on log seulement.
    """
    # Validation préalable
    error = _validate_lead_data(data, sender_phone)
    if error:
        logger.warning("Dispatch lead ignoré — %s | data=%s", error, data)
        return {"status": "error", "error": error}

    first_name       = (data.get("first_name") or "").strip()
    last_name        = (data.get("last_name") or "").strip()
    phone            = (data.get("phone") or "").strip() or sender_phone
    email            = (data.get("email") or "").strip() or None
    appointment_date = (data.get("appointment_date") or "").strip()

    if not phone:
        logger.warning(
            "Dispatch lead ignoré — phone manquant (ni dans LEAD_DATA ni sender_phone) | data=%s",
            data,
        )
        return {"status": "error", "error": "phone manquant"}

    logger.info(
        "Dispatch lead — %s %s | phone=%s | rdv=%s | email=%s",
        first_name, last_name, phone, appointment_date, email or "—",
    )

    # ── Tentative async via Django-Q2 ─────────────────────────────────────────
    use_async = getattr(settings, "KEMORA_LEAD_ASYNC", False)

    if use_async:
        try:
            from django_q.tasks import async_task
            async_task(
                "api.whatsapp.lead_service.create_lead_async",
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                email=email,
                sender_phone=sender_phone,
                appointment_date=appointment_date,
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
            return {"status": "queued"}

        except ImportError:
            logger.warning("Django-Q2 indisponible malgré KEMORA_LEAD_ASYNC=True — fallback synchrone")
        except Exception as exc:
            logger.warning("Django-Q2 erreur — fallback synchrone : %s", exc)

    # ── Fallback synchrone (défaut) ───────────────────────────────────────────
    from api.whatsapp.lead_service import create_lead_from_kemora
    result = create_lead_from_kemora(
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        email=email,
        sender_phone=sender_phone,
        appointment_date=appointment_date,
    )

    logger.info(
        "Lead dispatch synchrone terminé — status=%s lead_id=%s",
        result.get("status"), result.get("lead_id"),
    )
    return result


# ─── Point d'entrée principal ─────────────────────────────────────────────────

def generate_agent_reply(
    incoming_message: str,
    lead=None,
    sender_phone: Optional[str] = None,
    first_contact: bool = True,
) -> Optional[Tuple[str, Optional[dict]]]:
    """
    Génère la réponse de Kemora pour une conversation donnée.
    Chaque appel est totalement indépendant (stateless).

    Retourne (reply_text, lead_result) où :
      - reply_text  : le texte à envoyer au client (sans bloc LEAD_DATA)
      - lead_result : dict avec status/lead_id si un lead a été créé/mis à jour, sinon None
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
        lead_data   = _extract_lead_data(full_reply)
        lead_result = None

        if lead_data:
            # Nouveau client → création complète
            # Client connu avec nouveau RDV → mise à jour
            # Dans les deux cas, on passe par _dispatch_lead_creation
            # qui gère la logique created/updated dans lead_service
            lead_result = _dispatch_lead_creation(lead_data, sender_phone or "")

            if lead_result.get("status") == "error":
                logger.error(
                    "Échec création/mise à jour lead — error=%s | data=%s",
                    lead_result.get("error"), lead_data,
                )
            else:
                logger.info(
                    "Lead dispatch OK — status=%s lead_id=%s rdv=%s",
                    lead_result.get("status"),
                    lead_result.get("lead_id"),
                    lead_data.get("appointment_date"),
                )

        clean_reply = _strip_lead_marker(full_reply)

        logger.info(
            "Kemora — réponse | modèle=%s first=%s chars=%d lead_dispatched=%s lead_status=%s",
            _get_model_name(),
            first_contact,
            len(clean_reply),
            bool(lead_data),
            lead_result.get("status") if lead_result else "—",
        )
        return clean_reply, lead_result

    except Exception as exc:
        logger.exception("Erreur appel Gemini : %s", exc)
        return None