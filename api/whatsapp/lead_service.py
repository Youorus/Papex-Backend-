"""
LeadCreationService — Papiers Express

Crée un Lead depuis les données collectées par Kemora,
en passant par create_lead_with_side_effects qui déclenche
automatiquement l'AutomationEngine → handle_lead_created
→ SMS confirmation + Email confirmation.

Flux complet (nouveau client) :
    create_lead_from_kemora()
        → create_lead_with_side_effects()     [api/leads/creation.py]
            → LeadEvent.log("LEAD_CREATED")
                → AutomationEngine.handle()
                    → handle_lead_created()
                        → send_appointment_confirmation_sms_task()
                        → send_appointment_confirmation_task()   (si email)

Flux complet (client existant) :
    create_lead_from_kemora()
        → _update_existing_lead_appointment()
            → LeadEvent.log("APPOINTMENT_UPDATED")
                → send_appointment_confirmation_sms_task()  (direct)
                → send_appointment_confirmation_task()      (direct, si email)

Retourne un dict structuré pour que l'engine sache quoi confirmer à Kemora :
    {
        "status": "created" | "updated" | "error",
        "lead_id": int,
        "first_name": str,
        "last_name": str,
        "appointment_date": datetime,
    }

Champs collectés par Kemora : first_name, last_name, phone, email, appointment_date.
Pas de service_summary ni statut_dossier_id — non présents dans le modèle Lead.
"""

import logging
from typing import Optional

from django.db import transaction
from django.utils.dateparse import parse_datetime

from api.leads.constants import RDV_A_CONFIRMER
from api.leads.creation import create_lead_with_side_effects
from api.whatsapp.models import WhatsAppMessage, WhatsAppConversationSettings

logger = logging.getLogger(__name__)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _normalize_identity(value: Optional[str]) -> str:
    return (value or "").strip().capitalize()


def _normalize_phone(phone: Optional[str], fallback: Optional[str] = None) -> str:
    """
    Normalise un numéro de téléphone en format E.164 sans le +.

    Gère tous les formats courants :
        "07 53 65 82 05"        → "33753658205"
        "0753658205"            → "33753658205"
        "+33 7 53 65 82 05"     → "33753658205"
        "+33753658205"          → "33753658205"
        "33753658205"           → "33753658205"  (déjà correct)
        "0032487241425"         → "32487241425"  (Belgique)
        "+32 487 24 14 25"      → "32487241425"  (Belgique)

    Si le numéro est vide ou invalide, utilise le fallback (sender_phone).
    """
    raw = (phone or "").strip()

    # Retire tout sauf les chiffres et le +
    digits_only = "".join(c for c in raw if c.isdigit())

    if not digits_only:
        # Numéro vide → fallback sur sender_phone
        fallback_digits = "".join(c for c in (fallback or "") if c.isdigit())
        if fallback_digits.startswith("0"):
            fallback_digits = "33" + fallback_digits[1:]
        return fallback_digits

    # Commence par 00 → indicatif international (ex: 0033..., 0032...)
    if digits_only.startswith("00"):
        return digits_only[2:]

    # Commence par 0 → numéro local France → ajoute 33
    if digits_only.startswith("0"):
        return "33" + digits_only[1:]

    # Commence par 33, 32, 44, etc. → déjà en format international
    # On vérifie que c'est bien un indicatif connu (longueur >= 10 chiffres)
    if len(digits_only) >= 10:
        return digits_only

    # Cas court ou inconnu → fallback
    logger.warning("Numéro de téléphone court ou non reconnu : %r → fallback", raw)
    fallback_digits = "".join(c for c in (fallback or "") if c.isdigit())
    if fallback_digits.startswith("0"):
        fallback_digits = "33" + fallback_digits[1:]
    return fallback_digits or digits_only


def _parse_appointment_date(value: Optional[str]):
    """
    Parse une date ISO 8601.
    Retourne un datetime aware ou None.
    Raise ValueError si le format est invalide.
    """
    if not value:
        return None
    dt = parse_datetime(value)
    if dt is None:
        raise ValueError(f"appointment_date invalide ou non parseable : {value!r}")
    return dt


def _migrate_whatsapp_context(sender_phone: str, lead) -> None:
    """
    Rattache tous les messages WhatsApp existants (inconnus) au lead.
    Migre aussi les settings agent (activation/pause par conversation).
    """
    if not sender_phone:
        logger.warning("_migrate_whatsapp_context appelé sans sender_phone — skip")
        return

    rattached = WhatsAppMessage.objects.filter(
        lead__isnull=True,
        sender_phone=sender_phone,
    ).update(lead=lead)

    logger.info(
        "%d message(s) WhatsApp rattaché(s) au lead #%d",
        rattached, lead.pk,
    )

    # Migration des settings agent (pause/active)
    try:
        old = WhatsAppConversationSettings.objects.get(
            lead__isnull=True, sender_phone=sender_phone
        )
        agent_enabled = old.agent_enabled
        old.delete()
        WhatsAppConversationSettings.objects.get_or_create(
            lead=lead,
            defaults={"agent_enabled": agent_enabled},
        )
        logger.info(
            "Settings agent migrés vers lead #%d (agent_enabled=%s)",
            lead.pk, agent_enabled,
        )
    except WhatsAppConversationSettings.DoesNotExist:
        pass


def _update_existing_lead_appointment(lead, parsed_date, appointment_type: str) -> None:
    """
    Met à jour la date ET le type de RDV d'un lead existant.
    Envoie les confirmations SMS + email directement
    (l'AutomationEngine n'est pas branché sur APPOINTMENT_UPDATED).
    """
    from api.leads_events.models import LeadEvent
    from api.sms.tasks import send_appointment_confirmation_sms_task
    from api.utils.email.leads.tasks import send_appointment_confirmation_task

    old_date = lead.appointment_date
    old_type = getattr(lead, "appointment_type", None)

    lead.appointment_date = parsed_date
    lead.appointment_type = appointment_type
    lead.save(update_fields=["appointment_date", "appointment_type"])

    LeadEvent.log(
        lead=lead,
        event_code="APPOINTMENT_UPDATED",
        actor=None,
        data={
            "source": "whatsapp_agent_kemora",
            "channel": "whatsapp",
            "old_appointment_date": old_date.isoformat() if old_date else None,
            "new_appointment_date": parsed_date.isoformat(),
            "old_appointment_type": old_type,
            "new_appointment_type": appointment_type,
        },
    )

    # SMS de confirmation
    try:
        send_appointment_confirmation_sms_task(lead.id)
        logger.info("SMS confirmation envoyé pour lead #%d (mise à jour RDV)", lead.pk)
    except Exception as exc:
        logger.exception("Erreur envoi SMS confirmation (update RDV) lead #%d : %s", lead.pk, exc)

    # Email de confirmation si disponible
    if lead.email:
        try:
            send_appointment_confirmation_task(lead.id)
            logger.info("Email confirmation envoyé pour lead #%d (mise à jour RDV)", lead.pk)
        except Exception as exc:
            logger.exception("Erreur envoi email confirmation (update RDV) lead #%d : %s", lead.pk, exc)

    logger.info(
        "Lead #%d — RDV mis à jour : %s → %s | type : %s → %s",
        lead.pk,
        old_date,
        parsed_date.isoformat(),
        old_type,
        appointment_type,
    )


# ─── Création principale ──────────────────────────────────────────────────────

def create_lead_from_kemora(
    first_name: str,
    last_name: str,
    phone: str,
    email: Optional[str],
    sender_phone: str,
    appointment_date: str,
    appointment_type: str = "presentiel",  # "presentiel" | "visio"
) -> dict:
    """
    Crée (ou met à jour) un Lead depuis les données collectées par Kemora.

    Retourne un dict avec :
        - status : "created" | "updated" | "error"
        - lead_id : int (si succès)
        - first_name, last_name : str (pour le message de confirmation)
        - appointment_date : datetime (pour le message de confirmation)
        - error : str (si status == "error")
    """
    try:
        from api.lead_status.models import LeadStatus
        from api.leads.constants import LeadSource
        from api.leads.models import Lead

        # ── Nettoyage ─────────────────────────────────────────────────────────
        first_name       = _normalize_identity(first_name)
        last_name        = _normalize_identity(last_name)
        effective_phone  = _normalize_phone(phone, fallback=sender_phone)
        effective_email  = (email or "").strip() or None
        sender_phone     = "".join(c for c in (sender_phone or "") if c.isdigit())
        # Convertit les valeurs courtes de Kemora ("presentiel", "visio")
        # vers les constantes du modèle Lead ("PRESENTIEL", "VISIO_CONFERENCE").
        APPOINTMENT_TYPE_MAP = {
            "presentiel":       "PRESENTIEL",
            "presentiel":       "PRESENTIEL",
            "visio":            "VISIO_CONFERENCE",
            "visio_conference": "VISIO_CONFERENCE",
            "VISIO_CONFERENCE": "VISIO_CONFERENCE",
            "PRESENTIEL":       "PRESENTIEL",
            "telephone":        "TELEPHONE",
            "TELEPHONE":        "TELEPHONE",
        }
        raw_type = (appointment_type or "").strip().lower().replace("-", "_").replace(" ", "_")
        appointment_type = APPOINTMENT_TYPE_MAP.get(raw_type, "PRESENTIEL")

        # ── Validations ───────────────────────────────────────────────────────
        if not first_name or not last_name:
            logger.warning("Kemora — création ignorée : prénom/nom manquant")
            return {"status": "error", "error": "prénom/nom manquant"}

        if not effective_phone:
            logger.warning("Kemora — création ignorée : téléphone manquant (ni phone ni sender_phone)")
            return {"status": "error", "error": "téléphone manquant"}

        try:
            parsed_date = _parse_appointment_date(appointment_date)
        except ValueError as exc:
            logger.warning("Kemora — création ignorée : %s", exc)
            return {"status": "error", "error": str(exc)}

        if not parsed_date:
            logger.warning("Kemora — création ignorée : appointment_date manquante")
            return {"status": "error", "error": "appointment_date manquante"}

        # ── Lead déjà existant ? ──────────────────────────────────────────────
        # Recherche par numéro exact normalisé, puis par les 9 derniers chiffres
        # pour matcher peu importe le format stocké (0753..., 33753..., +33753...)
        phone_suffix = effective_phone[-9:] if len(effective_phone) >= 9 else effective_phone
        existing = (
            Lead.objects.filter(phone=effective_phone).first()
            or Lead.objects.filter(phone__endswith=phone_suffix).first()
        )

        if existing:
            logger.info(
                "Lead existant pour phone=%s — mise à jour RDV + rattachement WhatsApp",
                effective_phone,
            )
            with transaction.atomic():
                _update_existing_lead_appointment(existing, parsed_date, appointment_type)
                _migrate_whatsapp_context(sender_phone, existing)

            logger.info(
                "Lead #%d mis à jour par Kemora — rdv=%s",
                existing.pk, parsed_date.isoformat(),
            )
            return {
                "status": "updated",
                "lead_id": existing.pk,
                "first_name": existing.first_name,
                "last_name": existing.last_name,
                "appointment_date": parsed_date,
                "appointment_type": appointment_type,
            }

        # ── Statut par défaut ─────────────────────────────────────────────────
        try:
            default_status = LeadStatus.objects.get(code=RDV_A_CONFIRMER)
        except LeadStatus.DoesNotExist:
            default_status = LeadStatus.objects.order_by("id").first()
            logger.warning("Statut %s introuvable — fallback premier statut", RDV_A_CONFIRMER)

        # ── Source WhatsApp ───────────────────────────────────────────────────
        lead_source = getattr(LeadSource, "WHATSAPP", LeadSource.WEBSITE)

        lead_kwargs = {
            "first_name":        first_name,
            "last_name":         last_name,
            "phone":             effective_phone,
            "email":             effective_email,
            "status":            default_status,
            "source":            lead_source,
            "appointment_date":  parsed_date,
            "appointment_type":  appointment_type,
        }

        # ── Création atomique via le pipeline standard ────────────────────────
        with transaction.atomic():
            lead = create_lead_with_side_effects(
                actor=None,
                event_source="whatsapp_agent_kemora",
                event_data={
                    "sender_phone": sender_phone,
                    "channel":      "whatsapp",
                },
                lead_kwargs=lead_kwargs,
            )
            _migrate_whatsapp_context(sender_phone, lead)

        logger.info(
            "Lead créé par Kemora — id=%d %s %s phone=%s rdv=%s type=%s email=%s",
            lead.pk, first_name, last_name,
            effective_phone,
            parsed_date.isoformat(),
            appointment_type,
            effective_email or "—",
        )
        return {
            "status": "created",
            "lead_id": lead.pk,
            "first_name": lead.first_name,
            "last_name": lead.last_name,
            "appointment_date": parsed_date,
            "appointment_type": appointment_type,
        }

    except Exception as exc:
        logger.exception("Erreur création lead depuis Kemora : %s", exc)
        return {"status": "error", "error": str(exc)}


# ─── Point d'entrée Django-Q2 ─────────────────────────────────────────────────

def create_lead_async(
    first_name: str,
    last_name: str,
    phone: str,
    email: Optional[str],
    sender_phone: str,
    appointment_date: str,
    appointment_type: str = "presentiel",
) -> None:
    """
    Appelé par Django-Q2 worker en tâche de fond.
    """
    result = create_lead_from_kemora(
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        email=email,
        sender_phone=sender_phone,
        appointment_date=appointment_date,
        appointment_type=appointment_type,
    )

    if result["status"] in ("created", "updated"):
        logger.info(
            "create_lead_async OK — status=%s lead_id=%s",
            result["status"], result.get("lead_id"),
        )
    else:
        logger.error(
            "create_lead_async ÉCHEC — phone=%s error=%s",
            sender_phone, result.get("error"),
        )