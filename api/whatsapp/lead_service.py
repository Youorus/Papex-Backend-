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
            → LeadEvent.log("APPOINTMENT_UPDATED")  ← event dédié, pas LEAD_CREATED
                → AutomationEngine.handle()
                    → handle_appointment_updated()   ← handler dédié à implémenter si besoin
                        → send_appointment_confirmation_sms_task()
                        → send_appointment_confirmation_task()   (si email)
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


def _update_existing_lead_appointment(lead, parsed_date, service_summary: Optional[str]) -> None:
    """
    Si le lead existe déjà, on met à jour sa date de RDV.
    On utilise l'event code APPOINTMENT_UPDATED (et non LEAD_CREATED)
    pour éviter de re-déclencher toute la chaîne d'automation de création.

    Si l'AutomationEngine doit envoyer des notifications de confirmation
    pour les mises à jour de RDV, il faut implémenter handle_appointment_updated()
    dans handlers et le brancher dans l'engine.
    """
    from api.leads_events.models import LeadEvent
    from api.sms.tasks import send_appointment_confirmation_sms_task
    from api.utils.email.leads.tasks import send_appointment_confirmation_task

    old_date = lead.appointment_date
    lead.appointment_date = parsed_date
    lead.save(update_fields=["appointment_date"])

    # Log avec event code dédié — ne déclenche pas handle_lead_created
    LeadEvent.log(
        lead=lead,
        event_code="APPOINTMENT_UPDATED",
        actor=None,
        data={
            "source": "whatsapp_agent_kemora",
            "channel": "whatsapp",
            "old_appointment_date": old_date.isoformat() if old_date else None,
            "new_appointment_date": parsed_date.isoformat(),
            "service_summary": service_summary or "",
        },
    )

    # Envoi direct des notifications de confirmation (SMS + email si dispo)
    # car l'AutomationEngine n'est pas branché sur APPOINTMENT_UPDATED
    try:
        send_appointment_confirmation_sms_task(lead.id)
        logger.info("SMS confirmation envoyé pour lead #%d (mise à jour RDV)", lead.pk)
    except Exception as exc:
        logger.exception("Erreur envoi SMS confirmation (update RDV) lead #%d : %s", lead.pk, exc)

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
    service_summary: Optional[str],
    sender_phone: str,
    appointment_date: str,
    statut_dossier_id: Optional[int] = None,
):
    """
    Crée (ou met à jour) un Lead depuis les données collectées par Kemora.

    Nouveau client  → Lead créé + Client associé + LeadEvent(LEAD_CREATED)
                      → AutomationEngine → SMS confirmation + Email confirmation
    Client existant → appointment_date mis à jour + LeadEvent(APPOINTMENT_UPDATED)
                      → SMS + Email confirmation envoyés directement

    Dans les deux cas, les messages WhatsApp sont rattachés au lead
    et les settings agent migrent vers le lead connu.
    """
    try:
        from api.lead_status.models import LeadStatus
        from api.leads.constants import LeadSource
        from api.leads.models import Lead

        # ── Nettoyage ─────────────────────────────────────────────────────────
        first_name      = _normalize_identity(first_name)
        last_name       = _normalize_identity(last_name)
        # sender_phone est le fallback si phone est vide
        effective_phone = (phone or "").strip() or (sender_phone or "").strip()
        effective_email = (email or "").strip() or None
        sender_phone    = (sender_phone or "").strip()
        service_summary = (service_summary or "").strip() or None

        # ── Validations ───────────────────────────────────────────────────────
        if not first_name or not last_name:
            logger.warning("Kemora — création ignorée : prénom/nom manquant")
            return None

        if not effective_phone:
            logger.warning("Kemora — création ignorée : téléphone manquant (ni phone ni sender_phone)")
            return None

        parsed_date = _parse_appointment_date(appointment_date)
        if not parsed_date:
            logger.warning("Kemora — création ignorée : appointment_date manquante ou invalide")
            return None

        # ── Lead déjà existant ? ──────────────────────────────────────────────
        # Recherche par téléphone effectif (phone confirmé par la personne)
        # et par sender_phone (numéro WhatsApp) pour couvrir les deux cas
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
                _update_existing_lead_appointment(existing, parsed_date, service_summary)
                _migrate_whatsapp_context(sender_phone, existing)
            return existing

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
            "statut_dossier_id": statut_dossier_id,
        }

        # ── Création atomique via le pipeline standard ────────────────────────
        # create_lead_with_side_effects :
        #   1. Crée le Lead + Client associé
        #   2. LeadEvent.log("LEAD_CREATED")
        #   3. AutomationEngine.handle(event)
        #   4. handle_lead_created → SMS confirmation + Email confirmation
        with transaction.atomic():
            lead = create_lead_with_side_effects(
                actor=None,
                event_source="whatsapp_agent_kemora",
                event_data={
                    "service_summary": service_summary or "",
                    "sender_phone":    sender_phone,
                    "channel":         "whatsapp",
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
        return lead

    except Exception as exc:
        logger.exception("Erreur création lead depuis Kemora : %s", exc)
        return None


# ─── Point d'entrée Django-Q2 ─────────────────────────────────────────────────

def create_lead_async(
    first_name: str,
    last_name: str,
    phone: str,
    email: Optional[str],
    service_summary: Optional[str],
    sender_phone: str,
    appointment_date: str,
    statut_dossier_id: Optional[int] = None,
) -> None:
    """
    Appelé par Django-Q2 worker en tâche de fond.
    Ne bloque pas le webhook WhatsApp.
    """
    result = create_lead_from_kemora(
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        email=email,
        service_summary=service_summary,
        sender_phone=sender_phone,
        appointment_date=appointment_date,
        statut_dossier_id=statut_dossier_id,
    )

    if result:
        logger.info("create_lead_async OK — lead #%d", result.pk)
    else:
        logger.error("create_lead_async ÉCHEC — phone=%s", sender_phone)