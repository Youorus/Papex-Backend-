# api/leads/tasks.py

from datetime import timedelta

from django.utils import timezone
from django.db import transaction

from api.leads.models import Lead
from api.lead_status.models import LeadStatus
from api.leads.constants import (
    PRESENT,
    ABSENT,
    RDV_A_CONFIRMER,
    A_RAPPELER,
    RDV_CONFIRME,
    RDV_PLANIFIE,
)

from api.sms.tasks import (
    send_absent_urgency_sms_task,
    send_appointment_reminder_sms_task,
    send_appointment_reminder_48h_sms_task,
    send_appointment_reminder_24h_sms_task,
)
from api.utils.email.leads.tasks import (
    send_appointment_absent_email_task,
    send_appointment_reminder_email_task,  # ✅ Import ajouté
)

import logging
logger = logging.getLogger(__name__)


def mark_missed_appointments_as_absent():
    """
    1. Passe les leads en ABSENT si RDV passé et non PRESENT
    2. Déclenche un SMS + EMAIL pour chaque lead concerné
    """

    now = timezone.now()

    try:
        absent_status = LeadStatus.objects.get(code=ABSENT)
    except LeadStatus.DoesNotExist:
        logger.error("❌ Status ABSENT non trouvé dans la base")
        return "0 leads updated - Status ABSENT missing"

    # 🔥 Tous les RDV passés NON présent et NON absent
    leads_qs = Lead.objects.filter(
        appointment_date__isnull=False,
        appointment_date__lt=now,
    ).exclude(
        status__code__in=[PRESENT, ABSENT]
    )

    lead_ids = list(leads_qs.values_list("id", flat=True))

    if not lead_ids:
        logger.info("Aucun lead à marquer comme absent")
        return "0 leads updated"

    with transaction.atomic():
        updated_count = leads_qs.update(status=absent_status)

    # 🚀 Notifications async
    for lead_id in lead_ids:
        send_absent_urgency_sms_task(lead_id)
        send_appointment_absent_email_task(lead_id)
        logger.info(f"📢 Notifications envoyées pour lead #{lead_id} (absent)")

    return f"{updated_count} leads marked as ABSENT + SMS + EMAIL sent"


def send_appointment_reminders():
    """
    Envoie des rappels de rendez-vous :
    - 48h avant → SMS + EMAIL
    - 24h avant → SMS + EMAIL (urgence)

    Anti-doublon inclus
    """

    now = timezone.now()

    reminder_windows = [
        (timedelta(hours=48), "48h", send_appointment_reminder_48h_sms_task),
        (timedelta(hours=24), "24h", send_appointment_reminder_24h_sms_task),
    ]

    tolerance = timedelta(minutes=5)
    total_sent = 0

    for delta, label, sms_task_func in reminder_windows:
        target_time = now + delta
        window_start = target_time - tolerance
        window_end = target_time + tolerance

        leads = Lead.objects.filter(
            appointment_date__gte=window_start,
            appointment_date__lte=window_end,
            status__code__in=[RDV_CONFIRME, RDV_PLANIFIE],
        )

        for lead in leads:
            # 🔒 Anti doublon intelligent
            if lead.last_reminder_sent:
                if (now - lead.last_reminder_sent) < timedelta(hours=20):
                    logger.debug(f"Lead #{lead.id} - anti-doublon actif (rappel déjà envoyé)")
                    continue

            # 🚀 SMS + EMAIL
            sms_task_func(lead.id)
            send_appointment_reminder_email_task(lead.id)  # ✅ Maintenant fonctionnel

            # 🧠 tracking
            lead.last_reminder_sent = now
            lead.save(update_fields=["last_reminder_sent"])

            total_sent += 1
            logger.info(f"✅ Rappel {label} envoyé (SMS+EMAIL) pour lead #{lead.id}")

    return f"{total_sent} reminders sent (SMS+EMAIL)"