import os
import django

from api.leads.tasks import send_reminder_emails

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "papex.settings.prod")
django.setup()

from datetime import timedelta
from django.utils import timezone

from api.leads.models import Lead
from api.lead_status.models import LeadStatus
from api.leads.constants import RDV_CONFIRME

print("🧪 TEST RAPPEL J-1 EN PROD DB")

now = timezone.now()
tomorrow = now + timedelta(days=1)

status = LeadStatus.objects.get(code=RDV_CONFIRME)

lead = Lead.objects.create(
    first_name="Test",
    last_name="Prod",
    email="test-prod@example.com",
    phone="+33759650005",
    appointment_date=tomorrow,
    status=status,
    last_reminder_sent=None,
)

print(f"✅ Lead créé id={lead.id}")

send_reminder_emails()

lead.refresh_from_db()

print("last_reminder_sent =", lead.last_reminder_sent)
print("🎉 FIN DU TEST")