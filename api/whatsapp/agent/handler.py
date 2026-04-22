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
dans son message. On ne la regénère pas.
"""

import json
import logging
from typing import Optional, Tuple

from django.conf import settings
from django.db import transaction

from api.leads.models import Lead

from .prompt import (
    SYSTEM_PROMPT,
    GEMINI_MODEL_OVERRIDE,
    LEAD_DATA_MARKER,
    LEAD_DATA_END,
)
from ..models import WhatsAppMessage
from ..utils import (
    normalize_phone_for_meta,
    send_whatsapp_message,
    send_whatsapp_typing_indicator,
)

logger = logging.getLogger(__name__)

MAX_HISTORY_MESSAGES = 15
MAX_HISTORY_CHARS = 6_000
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
    lead=None,
    lead_first_name: Optional[str] = None,
    sender_phone: Optional[str] = None,
    first_contact: bool = True,
) -> str:
    from django.utils import timezone as tz
    import datetime
    from .prompt import IDF_DEPARTMENTS

    parts = []

    now = tz.localtime(tz.now())
    jours = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    mois = [
        "janvier", "février", "mars", "avril", "mai", "juin",
        "juillet", "août", "septembre", "octobre", "novembre", "décembre"
    ]
    demain = now + datetime.timedelta(days=1)
    apres_demain = now + datetime.timedelta(days=2)

    parts.append(
        f"[DATE_ACTUELLE: {jours[now.weekday()]} {now.day} {mois[now.month - 1]} {now.year} | "
        f"DEMAIN: {jours[demain.weekday()]} {demain.day} {mois[demain.month - 1]} {demain.year} | "
        f"APRÈS-DEMAIN: {jours[apres_demain.weekday()]} {apres_demain.day} {mois[apres_demain.month - 1]} {apres_demain.year} — "
        f"Utilise ces dates pour résoudre 'demain', 'après-demain', etc. Toujours demander confirmation.]"
    )

    if lead:
        crm = ["[CRM: CLIENT CONNU — utilise ces données, ne les redemande pas :"]
        crm.append(f"  Prénom      : {lead.first_name}")
        crm.append(f"  Nom         : {lead.last_name}")
        crm.append(f"  Téléphone   : {lead.phone}")
        crm.append(f"  Email       : {lead.email or '(non renseigné)'}")

        if hasattr(lead, "status") and lead.status:
            crm.append(f"  Statut lead : {lead.status.label} ({lead.status.code})")

        if getattr(lead, "statut_dossier", None):
            crm.append(f"  Statut dossier : {lead.statut_dossier.label}")

        if getattr(lead, "statut_dossier_interne", None):
            crm.append(f"  Statut dossier interne : {lead.statut_dossier_interne.label}")

        if getattr(lead, "appointment_date", None):
            apt = tz.localtime(lead.appointment_date)
            apt_str = (
                f"{jours[apt.weekday()]} {apt.day} {mois[apt.month - 1]} "
                f"{apt.year} à {apt.strftime('%H:%M')}"
            )
            apt_type = getattr(lead, "appointment_type", "presentiel") or "presentiel"
            crm.append(f"  RDV actuel  : {apt_str} ({apt_type})")
        else:
            crm.append("  RDV actuel  : (aucun planifié)")

        dept = (getattr(lead, "department_code", "") or "").strip()
        if dept:
            if dept in IDF_DEPARTMENTS:
                crm.append(f"  Département : {dept} → Île-de-France → RDV PRÉSENTIEL GRATUIT")
                crm.append("  TYPE_RDV    : presentiel")
            else:
                crm.append(f"  Département : {dept} → Hors Île-de-France → RDV VISIO 50€")
                crm.append("  TYPE_RDV    : visio")
        else:
            crm.append("  Département : (non renseigné — demander la localisation)")

        try:
            client = lead.form_data
            if client:
                if client.nationalite:
                    crm.append(f"  Nationalité  : {client.nationalite}")
                if client.pays:
                    crm.append(f"  Pays d'origine : {client.pays}")
                if client.ville or client.adresse:
                    loc = ", ".join(filter(None, [client.adresse, client.code_postal, client.ville]))
                    crm.append(f"  Adresse      : {loc}")

                    if not dept and client.code_postal:
                        cp_dept = client.code_postal[:2]
                        if cp_dept in IDF_DEPARTMENTS:
                            crm.append("  TYPE_RDV     : presentiel (déduit du code postal)")
                        else:
                            crm.append("  TYPE_RDV     : visio (déduit du code postal)")

                if client.situation_familiale:
                    crm.append(f"  Situation familiale : {client.situation_familiale}")
                if client.situation_pro:
                    crm.append(f"  Situation pro : {client.situation_pro}")
                if client.a_un_visa is not None:
                    visa_info = (
                        f"Oui ({client.type_visa})"
                        if client.a_un_visa and client.type_visa
                        else ("Oui" if client.a_un_visa else "Non")
                    )
                    crm.append(f"  Visa         : {visa_info}")
                if client.a_deja_eu_oqtf:
                    crm.append("  OQTF passée  : Oui")
                if client.a_des_enfants and client.nombre_enfants:
                    crm.append(
                        f"  Enfants      : {client.nombre_enfants} "
                        f"dont {client.nombre_enfants_francais or 0} français"
                    )
                if client.type_demande:
                    crm.append(f"  Type demande : {client.type_demande}")
                if client.date_entree_france:
                    crm.append(
                        f"  Entrée France : {client.date_entree_france.strftime('%d/%m/%Y')}"
                    )
                if client.remarques:
                    remarques = (
                        client.remarques[:200] + "…"
                        if len(client.remarques) > 200
                        else client.remarques
                    )
                    crm.append(f"  Remarques juriste : {remarques}")
        except Exception:
            pass

        crm.append(
            "→ NE REDEMANDE PAS ces informations. "
            "Utilise-les directement dans tes réponses et dans le bloc LEAD_DATA.]"
        )
        parts.append("\n".join(crm))

    elif lead_first_name:
        parts.append(f"[CRM: client partiellement connu, prénom = {lead_first_name}]")
    else:
        parts.append("[CRM: client inconnu — collecte toutes les informations, en commençant par la localisation]")

    if sender_phone:
        parts.append(
            f"[SENDER_PHONE: {sender_phone} — numéro WhatsApp de la personne. "
            f"Mentionne-le lors de la confirmation du téléphone si non connu du CRM.]"
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


# ─── Validation lead data ─────────────────────────────────────────────────────

def _validate_lead_data(data: dict, sender_phone: str) -> Optional[str]:
    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    appointment_date = (data.get("appointment_date") or "").strip()
    phone = (data.get("phone") or "").strip()

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
    """
    error = _validate_lead_data(data, sender_phone)
    if error:
        logger.warning("Dispatch lead ignoré — %s | data=%s", error, data)
        return {"status": "error", "error": error}

    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    phone = (data.get("phone") or "").strip() or sender_phone
    email = (data.get("email") or "").strip() or None
    appointment_date = (data.get("appointment_date") or "").strip()

    raw_appointment_type = (data.get("appointment_type") or "").strip().lower()

    APPOINTMENT_TYPE_MAP = {
        "presentiel": "PRESENTIEL",
        "visio": "VISIO_CONFERENCE",
    }

    appointment_type = APPOINTMENT_TYPE_MAP.get(raw_appointment_type)

    if not appointment_type:
        logger.warning(
            "Dispatch lead ignoré — appointment_type invalide | raw=%s | data=%s",
            raw_appointment_type,
            data,
        )
        return {"status": "error", "error": "appointment_type invalide"}

    if not phone:
        logger.warning(
            "Dispatch lead ignoré — phone manquant (ni dans LEAD_DATA ni sender_phone) | data=%s",
            data,
        )
        return {"status": "error", "error": "phone manquant"}

    logger.info(
        "Dispatch lead — %s %s | phone=%s | rdv=%s | type=%s | email=%s",
        first_name,
        last_name,
        phone,
        appointment_date,
        appointment_type,
        email or "—",
    )

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
                appointment_type=appointment_type,
                q_options={
                    "task_name": f"kemora_lead_{sender_phone}",
                    "timeout": 60,
                    "max_attempts": 2,
                },
            )
            logger.info(
                "Lead dispatché via Django-Q2 — %s %s rdv=%s type=%s",
                first_name,
                last_name,
                appointment_date,
                appointment_type,
            )
            return {"status": "queued"}

        except ImportError:
            logger.warning("Django-Q2 indisponible malgré KEMORA_LEAD_ASYNC=True — fallback synchrone")
        except Exception as exc:
            logger.warning("Django-Q2 erreur — fallback synchrone : %s", exc)

    from api.whatsapp.lead_service import create_lead_from_kemora
    result = create_lead_from_kemora(
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        email=email,
        sender_phone=sender_phone,
        appointment_date=appointment_date,
        appointment_type=appointment_type,
    )

    logger.info(
        "Lead dispatch synchrone terminé — status=%s lead_id=%s",
        result.get("status"),
        result.get("lead_id"),
    )
    return result


# ─── Point d'entrée principal du moteur ───────────────────────────────────────

def generate_agent_reply(
    incoming_message: str,
    lead=None,
    sender_phone: Optional[str] = None,
    first_contact: bool = True,
) -> Optional[Tuple[str, Optional[dict]]]:
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

    try:
        prompt = _build_prompt(
            incoming_message=incoming_message,
            history_text=history_text,
            lead=lead,
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

        lead_data = _extract_lead_data(full_reply)
        lead_result = None

        if lead_data:
            lead_result = _dispatch_lead_creation(lead_data, sender_phone or "")

            if lead_result.get("status") == "error":
                logger.error(
                    "Échec création/mise à jour lead — error=%s | data=%s",
                    lead_result.get("error"),
                    lead_data,
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


# ─── Wrapper appelé par Django-Q2 ─────────────────────────────────────────────

def trigger_agent_response(
    incoming_body: str,
    sender_phone: str,
    lead_id: Optional[int] = None,
    wa_message_id: str = "",
):
    """
    Point d'entrée attendu par Django-Q2 :
      api.whatsapp.agent.handler.trigger_agent_response

    Cette fonction :
      - charge le lead si lead_id existe,
      - envoie le typing indicator si wa_message_id est présent,
      - génère la réponse Kemora,
      - envoie le message via Meta,
      - sauvegarde le message sortant en base.
    """
    logger.info(
        "trigger_agent_response START | phone=%s | lead_id=%s | wa_message_id=%s",
        sender_phone,
        lead_id,
        wa_message_id,
    )

    lead = None
    if lead_id:
        try:
            lead = Lead.objects.get(id=lead_id)
        except Lead.DoesNotExist:
            logger.warning(
                "Lead introuvable dans trigger_agent_response | lead_id=%s",
                lead_id,
            )

    try:
        # 1) Typing indicator immédiatement
        if wa_message_id:
            send_whatsapp_typing_indicator(wa_message_id)
        else:
            logger.info(
                "Typing indicator non envoyé | wa_message_id absent | phone=%s",
                sender_phone,
            )

        # 2) Déterminer si c'est le premier message sortant
        previous_outbound_exists = WhatsAppMessage.objects.filter(
            sender_phone=sender_phone,
            is_outbound=True,
        ).exists()

        first_contact = not previous_outbound_exists

        # 3) Générer la réponse IA
        result = generate_agent_reply(
            incoming_message=incoming_body,
            lead=lead,
            sender_phone=sender_phone,
            first_contact=first_contact,
        )

        if not result:
            logger.warning("Kemora n'a généré aucune réponse | phone=%s", sender_phone)
            return None

        reply_text, lead_result = result

        if not reply_text or not reply_text.strip():
            logger.warning("Kemora a généré une réponse vide | phone=%s", sender_phone)
            return None

        # 4) Si lead créé pendant la génération, on recharge
        if not lead and lead_result and lead_result.get("lead_id"):
            try:
                lead = Lead.objects.get(id=lead_result["lead_id"])
            except Lead.DoesNotExist:
                logger.warning(
                    "Lead créé/maj annoncé mais introuvable après génération | lead_id=%s",
                    lead_result.get("lead_id"),
                )

        # 5) Envoi du vrai message WhatsApp
        to_phone = normalize_phone_for_meta(sender_phone)
        meta_response = send_whatsapp_message(to_phone, reply_text)

        outbound_wa_id = (
            meta_response.get("messages", [{}])[0].get("id")
            or f"out_{to_phone}"
        )

        # 6) Sauvegarde BDD
        with transaction.atomic():
            saved = WhatsAppMessage.objects.create(
                wa_id=outbound_wa_id,
                lead=lead,
                sender_phone=to_phone,
                body=reply_text,
                is_outbound=True,
                is_read=True,
                delivery_status="sent",
            )

        logger.info(
            "trigger_agent_response SUCCESS | db_id=%s | wa_id=%s | phone=%s | lead_id=%s",
            saved.id,
            outbound_wa_id,
            to_phone,
            getattr(lead, "id", None),
        )

        return {
            "status": "sent",
            "message_id": saved.id,
            "wa_id": outbound_wa_id,
            "lead_id": getattr(lead, "id", None),
        }

    except Exception as exc:
        logger.exception(
            "trigger_agent_response ERROR | phone=%s | lead_id=%s | error=%s",
            sender_phone,
            lead_id,
            exc,
        )
        raise