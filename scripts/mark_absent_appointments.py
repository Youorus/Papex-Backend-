# scripts/mark_absent_appointments.py

import os
import django
from django.utils import timezone

# 🔧 Initialisation Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "papex.settings.prod")
django.setup()

from api.leads.models import Lead
from api.leads.constants import (
    RDV_A_CONFIRMER,
    RDV_CONFIRME,
    ABSENT,
)
from api.lead_status.models import LeadStatus


def run():
    now = timezone.now()

    try:
        absent_status = LeadStatus.objects.get(code=ABSENT)
    except LeadStatus.DoesNotExist:
        print("❌ Statut ABSENT introuvable")
        return

    leads = Lead.objects.filter(
        appointment_date__isnull=False,
        appointment_date__lt=now,
        status__code__in=[RDV_A_CONFIRMER, RDV_CONFIRME],
    )

    print(f"🔎 {leads.count()} rendez-vous dépassé(s)")

    updated = 0

    for lead in leads:
        lead.status = absent_status
        lead.save(update_fields=["status"])
        updated += 1

        print(f"➡️ Lead #{lead.id} → ABSENT")

    print(f"✅ Terminé — {updated} lead(s) mis en ABSENT")


if __name__ == "__main__":
    run()
