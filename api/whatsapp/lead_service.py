"""
LeadCreationService — Papiers Express

Crée un Lead depuis les données collectées par Kemia,
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

Retourne un dict structuré pour que l'engine sache quoi confirmer à Kemia :
    {
        "status": "created" | "updated" | "error",
        "lead_id": int,
        "first_name": str,
        "last_name": str,
        "appointment_date": datetime,
    }

Champs collectés par Kemia : first_name, last_name, phone, email, appointment_date, situation_summary.
"""

import logging
from typing import Optional

from django.db import transaction
from django.utils.dateparse import parse_datetime
from django.core.cache import cache
import contextlib

from api.leads.constants import RDV_A_CONFIRMER
from api.leads.creation import create_lead_with_side_effects
from api.whatsapp.models import WhatsAppMessage, WhatsAppConversationSettings
from api.comments.models import Comment

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def appointment_slot_lock(parsed_date):
    """
    Lock Redis pour éviter que deux personnes réservent le même créneau 
    à la même microseconde via l'IA.
    """
    lock_key = f"lock_apt_{parsed_date.isoformat()}"
    # On tente de poser un verrou de 30 secondes
    acquired = cache.add(lock_key, "locked", timeout=30)
    try:
        yield acquired
    finally:
        if acquired:
            cache.delete(lock_key)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _normalize_identity(value: Optional[str]) -> str:
    return (value or "").strip().capitalize()


def _normalize_phone(phone: Optional[str], fallback: Optional[str] = None) -> str:
    """
    Normalise un numéro de téléphone en format E.164 sans le +.
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
    """
    if not sender_phone:
        return

    WhatsAppMessage.objects.filter(
        lead__isnull=True,
        sender_phone=sender_phone,
    ).update(lead=lead)

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
    except WhatsAppConversationSettings.DoesNotExist:
        pass


def _add_situation_summary_comment(lead, summary: str):
    """
    Ajoute un commentaire de synthèse sur la situation du client pour le juriste.
    """
    if not summary or not summary.strip():
        return

    try:
        # On crée le commentaire. L'auteur est None (système).
        Comment.objects.create(
            lead=lead,
            content=f"📝 **Synthèse IA - Situation du client** :\n\n{summary.strip()}",
            author=None 
        )
        logger.info("Commentaire de synthèse ajouté pour le lead #%d", lead.pk)
    except Exception as exc:
        logger.error("Erreur lors de l'ajout du commentaire de synthèse : %s", exc)


def _update_existing_lead_appointment(lead, parsed_date, appointment_type: str, situation_summary: str = "") -> None:
    """
    Met à jour la date ET le type de RDV d'un lead existant.
    """
    from api.leads_events.models import LeadEvent
    from api.sms.tasks import send_appointment_confirmation_sms_task
    from api.utils.email.leads.tasks import (
        send_appointment_confirmation_task,
        send_visio_payment_task
    )

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
    
    # On rajoute quand même la synthèse si elle a changé ou si c'est un nouveau rdv
    if situation_summary:
        _add_situation_summary_comment(lead, situation_summary)

    # SMS de confirmation
    try:
        send_appointment_confirmation_sms_task(lead.id)
    except Exception as exc:
        logger.exception("Erreur envoi SMS confirmation (update RDV) lead #%d : %s", lead.pk, exc)

    # Email de confirmation / paiement visio
    if lead.email:
        try:
            if appointment_type == "VISIO_CONFERENCE":
                send_visio_payment_task(lead.id)
            else:
                send_appointment_confirmation_task(lead.id)
        except Exception as exc:
            logger.exception("Erreur envoi email confirmation (update RDV) lead #%d : %s", lead.pk, exc)


# ─── Création principale ──────────────────────────────────────────────────────

def create_lead_from_kemora(
    first_name: str,
    last_name: str,
    phone: str,
    email: Optional[str],
    sender_phone: str,
    appointment_date: str,
    appointment_type: str = "presentiel",
    situation_summary: str = "",
    promo_code: Optional[str] = None,
) -> dict:
    """
    Crée (ou met à jour) un Lead depuis les données collectées par Kemia.
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
        
        APPOINTMENT_TYPE_MAP = {
            "presentiel":       "PRESENTIEL",
            "visio":            "VISIO_CONFERENCE",
            "visio_conference": "VISIO_CONFERENCE",
            "telephone":        "TELEPHONE",
        }
        raw_type = (appointment_type or "").strip().lower().replace("-", "_").replace(" ", "_")
        appointment_type = APPOINTMENT_TYPE_MAP.get(raw_type, "PRESENTIEL")

        # ── Validations ───────────────────────────────────────────────────────
        if not first_name or not last_name:
            return {"status": "error", "error": "prénom/nom manquant"}

        if not effective_phone:
            return {"status": "error", "error": "téléphone manquant"}

        try:
            parsed_date = _parse_appointment_date(appointment_date)
        except ValueError as exc:
            return {"status": "error", "error": str(exc)}

        if not parsed_date:
            return {"status": "error", "error": "appointment_date manquante"}

        # ── Promo Code ────────────────────────────────────────────────────────
        promo_code_obj = None
        creator_profile = None
        if promo_code:
            from api.creators.models import PromoCode
            try:
                promo_code_obj = PromoCode.objects.select_related("creator").get(
                    code__iexact=promo_code.strip(),
                    status=PromoCode.Status.ACTIVE
                )
                creator_profile = promo_code_obj.creator
                # Ajoute une note à la synthèse pour le juriste
                summary_addition = f"Code promo appliqué : {promo_code_obj.code} ({creator_profile.user.get_full_name()})"
                situation_summary = f"{situation_summary}\n{summary_addition}".strip()

            except PromoCode.DoesNotExist:
                logger.warning("Code promo fourni par Kemia introuvable ou inactif: %s", promo_code)
                # On ne bloque pas la création, on log simplement.

        # ── Lead déjà existant ? ──────────────────────────────────────────────
        phone_suffix = effective_phone[-9:] if len(effective_phone) >= 9 else effective_phone
        existing = (
            Lead.objects.filter(phone=effective_phone).first()
            or Lead.objects.filter(phone__endswith=phone_suffix).first()
        )

        with appointment_slot_lock(parsed_date) as acquired:
            if not acquired:
                logger.warning("Conflit de réservation pour le créneau %s", parsed_date)
                return {"status": "error", "error": "Ce créneau vient d'être réservé par une autre personne."}

            if existing:
                with transaction.atomic():
                    _update_existing_lead_appointment(existing, parsed_date, appointment_type, situation_summary)
                    if promo_code_obj:
                        existing.promo_code = promo_code_obj
                        existing.creator_profile = creator_profile
                        existing.save(update_fields=["promo_code", "creator_profile"])
                    _migrate_whatsapp_context(sender_phone, existing)

                return {
                    "status": "updated",
                    "lead_id": existing.pk,
                    "first_name": existing.first_name,
                    "last_name": existing.last_name,
                    "appointment_date": parsed_date,
                    "appointment_type": appointment_type,
                }

            # ── Création ──────────────────────────────────────────────────────────
            try:
                default_status = LeadStatus.objects.get(code=RDV_A_CONFIRMER)
            except LeadStatus.DoesNotExist:
                default_status = LeadStatus.objects.order_by("id").first()

            lead_source = getattr(LeadSource, "KEMORA", LeadSource.WEBSITE)

            lead_kwargs = {
                "first_name":        first_name,
                "last_name":         last_name,
                "phone":             effective_phone,
                "email":             effective_email,
                "status":            default_status,
                "source":            lead_source,
                "appointment_date":  parsed_date,
                "appointment_type":  appointment_type,
                "promo_code":        promo_code_obj,
                "creator_profile":   creator_profile,
            }

            with transaction.atomic():
                from api.utils.email.leads.tasks import send_visio_payment_task
                
                # On désactive la confirmation email standard pour la gérer nous-mêmes
                lead = create_lead_with_side_effects(
                    actor=None,
                    event_source="whatsapp_agent_kemora",
                    event_data={
                        "sender_phone": sender_phone,
                        "channel": "whatsapp",
                        "skip_email_confirmation": True, 
                    },
                    lead_kwargs=lead_kwargs,
                )
                _migrate_whatsapp_context(sender_phone, lead)
                
                # AJOUT DU COMMENTAIRE DE SYNTHÈSE PROFESSIONNEL
                if situation_summary:
                    _add_situation_summary_comment(lead, situation_summary)

                # Envoi manuel de l'email correct (paiement ou confirmation)
                if effective_email:
                    if appointment_type == "VISIO_CONFERENCE":
                        send_visio_payment_task(lead.id)
                    else:
                        # Si ce n'est pas une visio, on envoie la confirmation classique
                        from api.utils.email.leads.tasks import send_appointment_confirmation_task
                        send_appointment_confirmation_task(lead.id)

            return {
                "status": "created",
                "lead_id": lead.pk,
                "first_name": lead.first_name,
                "last_name": lead.last_name,
                "appointment_date": parsed_date,
                "appointment_type": appointment_type,
            }

    except Exception as exc:
        logger.exception("Erreur création lead depuis Kemia : %s", exc)
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
    situation_summary: str = "",
) -> None:
    """
    Appelé par Django-Q2 worker.
    """
    create_lead_from_kemora(
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        email=email,
        sender_phone=sender_phone,
        appointment_date=appointment_date,
        appointment_type=appointment_type,
        situation_summary=situation_summary,
    )
