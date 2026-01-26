import logging
from datetime import datetime, timedelta, time

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from api.lead_status.models import LeadStatus
from api.leads.constants import ABSENT, RDV_CONFIRME
from api.leads.models import Lead
from api.sms.notifications.leads import send_appointment_reminder_sms
from api.utils.email import (
    send_appointment_reminder_email,
    send_missed_appointment_email,
)

logger = logging.getLogger(__name__)


# ============================================================
# ⏰ RAPPEL J-1 — EMAIL + SMS
# ============================================================

@shared_task(bind=True)
def send_appointment_reminders():
    now = timezone.now()

    start = now + timedelta(hours=47, minutes=30)
    end   = now + timedelta(hours=48, minutes=30)

    leads = Lead.objects.filter(
        appointment_date__range=(start, end),
        last_reminder_sent__isnull=True,
    )

    for lead in leads:
        email_ok = False
        sms_ok = False

        if lead.email:
            try:
                send_appointment_reminder_email(lead)
                email_ok = True
            except Exception:
                pass

        if lead.phone:
            try:
                send_appointment_reminder_sms(lead)
                sms_ok = True
            except Exception:
                pass

        if email_ok or sms_ok:
            lead.last_reminder_sent = now
            lead.save(update_fields=["last_reminder_sent"])


# ============================================================
# 🚫 MARQUER ABSENT + EMAIL
# ============================================================

@shared_task(bind=True)
def mark_absent_leads():
    now = timezone.now()

    absent_status = LeadStatus.objects.get(code=ABSENT)

    leads = Lead.objects.filter(
        appointment_date__lt=now,
        status__code__in=[RDV_CONFIRME],
    )

    for lead in leads:
        lead.status = absent_status
        lead.save(update_fields=["status"])

        if lead.email:
            send_missed_appointment_email(lead)
