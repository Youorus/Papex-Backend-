import logging
from typing import Optional

from django.db import transaction
from django.utils.dateparse import parse_datetime


from api.leads.constants import RDV_A_CONFIRMER
from api.leads.creation import create_lead_with_side_effects
from api.whatsapp.models import WhatsAppMessage, WhatsAppConversationSettings

logger = logging.getLogger(__name__)


def _normalize_identity(value: Optional[str]) -> str:
    return (value or "").strip().capitalize()


def _parse_appointment_date(value: Optional[str]):
    if not value:
        return None

    dt = parse_datetime(value)
    if dt is None:
        raise ValueError(f"appointment_date invalide: {value}")

    return dt


def _migrate_whatsapp_context(sender_phone: str, lead) -> None:
    rattached = WhatsAppMessage.objects.filter(
        lead__isnull=True,
        sender_phone=sender_phone,
    ).update(lead=lead)

    logger.info(
        "%d message(s) WhatsApp rattaché(s) au lead #%d",
        rattached,
        lead.pk,
    )

    try:
        old_settings = WhatsAppConversationSettings.objects.get(
            lead__isnull=True,
            sender_phone=sender_phone,
        )
        agent_enabled = old_settings.agent_enabled
        old_settings.delete()

        WhatsAppConversationSettings.objects.get_or_create(
            lead=lead,
            defaults={"agent_enabled": agent_enabled},
        )
    except WhatsAppConversationSettings.DoesNotExist:
        pass


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
    try:
        from api.lead_status.models import LeadStatus
        from api.leads.constants import LeadSource
        from api.leads.models import Lead

        first_name = _normalize_identity(first_name)
        last_name = _normalize_identity(last_name)
        effective_phone = (phone or "").strip() or (sender_phone or "").strip()
        effective_email = (email or "").strip() or None
        sender_phone = (sender_phone or "").strip()
        service_summary = (service_summary or "").strip() or None

        if not first_name or not last_name:
            logger.warning("Kemora — création lead ignorée : prénom/nom manquant")
            return None

        if not effective_phone:
            logger.warning("Kemora — création lead ignorée : téléphone manquant")
            return None

        parsed_appointment_date = _parse_appointment_date(appointment_date)
        if not parsed_appointment_date:
            logger.warning("Kemora — création lead ignorée : appointment_date manquante")
            return None

        existing = Lead.objects.filter(phone=effective_phone).first()
        if existing:
            logger.info(
                "Lead déjà existant pour phone=%s — rattachement WhatsApp seulement",
                effective_phone,
            )
            _migrate_whatsapp_context(sender_phone, existing)
            return existing

        try:
            default_status = LeadStatus.objects.get(code=RDV_A_CONFIRMER)
        except LeadStatus.DoesNotExist:
            default_status = LeadStatus.objects.order_by("id").first()
            logger.warning(
                "Statut %s introuvable, fallback sur le premier statut",
                RDV_A_CONFIRMER,
            )

        lead_source = getattr(LeadSource, "WHATSAPP", LeadSource.WEBSITE)

        lead_kwargs = {
            "first_name": first_name,
            "last_name": last_name,
            "phone": effective_phone,
            "email": effective_email,
            "status": default_status,
            "source": lead_source,
            "appointment_date": parsed_appointment_date,
            "statut_dossier_id": statut_dossier_id,
        }

        with transaction.atomic():
            lead = create_lead_with_side_effects(
                actor=None,
                event_source="whatsapp_agent_kemora",
                event_data={
                    "service_summary": service_summary or "",
                    "sender_phone": sender_phone,
                    "channel": "whatsapp",
                },
                lead_kwargs=lead_kwargs,
            )

            _migrate_whatsapp_context(sender_phone, lead)

            logger.info(
                "Lead créé par Kemora — id=%d phone=%s appointment_date=%s",
                lead.pk,
                effective_phone,
                parsed_appointment_date.isoformat(),
            )

        return lead

    except Exception as exc:
        logger.exception("Erreur création lead depuis Kemora : %s", exc)
        return None


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
        logger.info("Tâche async create_lead_async terminée — lead #%d", result.pk)
    else:
        logger.error("Tâche async create_lead_async échouée pour phone=%s", sender_phone)