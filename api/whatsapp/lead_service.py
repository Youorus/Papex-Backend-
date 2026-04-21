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


def _update_existing_lead_appointment(lead, parsed_date) -> None:
    """
    Met à jour la date de RDV d'un lead existant.
    Envoie les confirmations SMS + email directement
    (l'AutomationEngine n'est pas branché sur APPOINTMENT_UPDATED).
    """
    from api.leads_events.models import LeadEvent
    from api.sms.tasks import send_appointment_confirmation_sms_task
    from api.utils.email.leads.tasks import send_appointment_confirmation_task

    old_date = lead.appointment_date
    lead.appointment_date = parsed_date
    lead.save(update_fields=["appointment_date"])

    LeadEvent.log(
        lead=lead,
        event_code="APPOINTMENT_UPDATED",
        actor=None,
        data={
            "source": "whatsapp_agent_kemora",
            "channel": "whatsapp",
            "old_appointment_date": old_date.isoformat() if old_date else None,
            "new_appointment_date": parsed_date.isoformat(),
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
        "Lead #%d — RDV mis à jour : %s → %s",
        lead.pk,
        old_date,
        parsed_date.isoformat(),
    )


# ─── Création principale ──────────────────────────────────────────────────────

def create_lead_from_kemora(
    first_name: str,
    last_name: str,
    phone: str,
    email: Optional[str],
    sender_phone: str,
    appointment_date: str,
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
        first_name      = _normalize_identity(first_name)
        last_name       = _normalize_identity(last_name)
        effective_phone = (phone or "").strip() or (sender_phone or "").strip()
        effective_email = (email or "").strip() or None
        sender_phone    = (sender_phone or "").strip()

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
        existing = (
            Lead.objects.filter(phone=effective_phone).first()
            or (
                Lead.objects.filter(phone=sender_phone).first()
                if sender_phone and sender_phone != effective_phone
                else None
            )
        )

        if existing:
            logger.info(
                "Lead existant pour phone=%s — mise à jour RDV + rattachement WhatsApp",
                effective_phone,
            )
            with transaction.atomic():
                _update_existing_lead_appointment(existing, parsed_date)
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
            "first_name":       first_name,
            "last_name":        last_name,
            "phone":            effective_phone,
            "email":            effective_email,
            "status":           default_status,
            "source":           lead_source,
            "appointment_date": parsed_date,
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
            "Lead créé par Kemora — id=%d %s %s phone=%s rdv=%s email=%s",
            lead.pk, first_name, last_name,
            effective_phone,
            parsed_date.isoformat(),
            effective_email or "—",
        )
        return {
            "status": "created",
            "lead_id": lead.pk,
            "first_name": lead.first_name,
            "last_name": lead.last_name,
            "appointment_date": parsed_date,
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
) -> None:
    """
    Appelé par Django-Q2 worker en tâche de fond.
    Ne bloque pas le webhook WhatsApp.
    Note : dans ce mode async, on ne peut pas renvoyer de message à l'utilisateur.
    La confirmation a déjà été envoyée de manière optimiste par l'engine.
    """
    result = create_lead_from_kemora(
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        email=email,
        sender_phone=sender_phone,
        appointment_date=appointment_date,
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