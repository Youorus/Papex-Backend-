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
    lead=None,                        # ← objet Lead complet pour injection CRM
    lead_first_name: Optional[str] = None,
    sender_phone: Optional[str] = None,
    first_contact: bool = True,
) -> str:
    from django.utils import timezone as tz
    parts = []

    # ── Date actuelle ─────────────────────────────────────────────────────────
    now   = tz.localtime(tz.now())
    jours = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    mois  = ["janvier", "février", "mars", "avril", "mai", "juin",
             "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    date_str     = f"{jours[now.weekday()]} {now.day} {mois[now.month - 1]} {now.year}"
    demain       = now + __import__("datetime").timedelta(days=1)
    demain_str   = f"{jours[demain.weekday()]} {demain.day} {mois[demain.month - 1]} {demain.year}"
    heure_str = now.strftime("%H:%M")
    parts.append(
        f"[DATE_ACTUELLE: {date_str} {heure_str} | DEMAIN: {demain_str} — "
        f"Utilise ces dates pour résoudre 'demain', 'après-demain', etc. "
        f"RÈGLE CRITIQUE : ne propose JAMAIS un rendez-vous à une date ou heure DÉJÀ PASSÉE. "
        f"La date ET l'heure du RDV doivent être strictement FUTURES par rapport à {date_str} {heure_str}. "
        f"Toujours demander confirmation avant de générer le bloc.]"
    )

    # ── Données CRM enrichies ─────────────────────────────────────────────────
    from .prompt import IDF_DEPARTMENTS
    import datetime as _dt

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

        if lead.appointment_date:
            apt     = tz.localtime(lead.appointment_date)
            apt_str = f"{jours[apt.weekday()]} {apt.day} {mois[apt.month - 1]} {apt.year} à {apt.strftime('%H:%M')}"
            apt_type = getattr(lead, "appointment_type", "presentiel") or "presentiel"
            crm.append(f"  RDV actuel  : {apt_str} ({apt_type})")
        else:
            crm.append("  RDV actuel  : (aucun planifié)")

        # Localisation → détermine le type de RDV
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

        # Données dossier client enrichies (form_data)
        try:
            client = getattr(lead, "form_data", None)
            if client:
                if getattr(client, "nationalite", None):
                    crm.append(f"  Nationalité  : {client.nationalite}")
                if getattr(client, "pays", None):
                    crm.append(f"  Pays origine : {client.pays}")
                ville  = getattr(client, "ville", None)
                adresse = getattr(client, "adresse", None)
                cp     = getattr(client, "code_postal", None)
                if ville or adresse:
                    loc = ", ".join(filter(None, [adresse, cp, ville]))
                    crm.append(f"  Adresse      : {loc}")
                    if not dept and cp:
                        cp_dept = str(cp)[:2]
                        if cp_dept in IDF_DEPARTMENTS:
                            crm.append("  TYPE_RDV     : presentiel (déduit code postal)")
                        else:
                            crm.append("  TYPE_RDV     : visio (déduit code postal)")
                sit_fam = getattr(client, "situation_familiale", None)
                if sit_fam:
                    crm.append(f"  Situation familiale : {sit_fam}")
                sit_pro = getattr(client, "situation_pro", None)
                if sit_pro:
                    crm.append(f"  Situation pro : {sit_pro}")
                a_visa = getattr(client, "a_un_visa", None)
                if a_visa is not None:
                    type_visa = getattr(client, "type_visa", None)
                    visa_info = f"Oui ({type_visa})" if a_visa and type_visa else ("Oui" if a_visa else "Non")
                    crm.append(f"  Visa         : {visa_info}")
                if getattr(client, "a_deja_eu_oqtf", None):
                    crm.append("  OQTF passée  : Oui")
                nb_enf = getattr(client, "nombre_enfants", None)
                if getattr(client, "a_des_enfants", None) and nb_enf:
                    nb_fr = getattr(client, "nombre_enfants_francais", 0) or 0
                    crm.append(f"  Enfants      : {nb_enf} dont {nb_fr} français")
                type_dem = getattr(client, "type_demande", None)
                if type_dem:
                    crm.append(f"  Type demande : {type_dem}")
                date_entree = getattr(client, "date_entree_france", None)
                if date_entree:
                    crm.append(f"  Entrée France : {date_entree.strftime('%d/%m/%Y')}")
                remarques = getattr(client, "remarques", None)
                if remarques:
                    r = remarques[:200] + "…" if len(remarques) > 200 else remarques
                    crm.append(f"  Remarques juriste : {r}")
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

    # ── Numéro WhatsApp ───────────────────────────────────────────────────────
    if sender_phone:
        parts.append(
            f"[SENDER_PHONE: {sender_phone} — numéro WhatsApp de la personne. "
            f"Mentionne-le lors de la confirmation du téléphone si non connu du CRM.]"
        )

    # ── État de la conversation ───────────────────────────────────────────────
    if first_contact:
        parts.append(
            "[ÉTAT: PREMIER CONTACT — c'est le premier message de cette personne. "
            "Répondez directement à sa question ou demandez simplement comment vous pouvez l'aider. "
            "NE PAS vous présenter par votre nom. NE PAS dire 'Je suis Kemora'. "
            "Un 'Bonjour 😊' suffit si besoin d'une accroche. Restez naturel.]"
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

    # ── Validation date non passée ────────────────────────────────────────────
    try:
        from django.utils import timezone as tz
        from django.utils.dateparse import parse_datetime
        parsed = parse_datetime(appointment_date)
        if parsed is not None:
            now = tz.now()
            if parsed.tzinfo is None:
                import datetime
                parsed = parsed.replace(tzinfo=datetime.timezone.utc)
            if parsed <= now:
                logger.warning(
                    "LEAD_DATA rejeté — date passée : %s (now=%s)", appointment_date, now
                )
                return f"appointment_date dans le passé ({appointment_date})"
    except Exception as exc:
        logger.warning("Validation date passée échouée (non bloquant) : %s", exc)

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
    appointment_type = (data.get("appointment_type") or "presentiel").strip()
    if appointment_type not in ("presentiel", "visio"):
        appointment_type = "presentiel"

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
                appointment_type=appointment_type,
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
        appointment_type=appointment_type,
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