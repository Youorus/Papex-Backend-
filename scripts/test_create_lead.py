import os
import sys
import django
from django.utils import timezone

from api.leads.constants import RDV_A_CONFIRMER
from api.leads_events.models import LeadEvent

# 📌 Ajouter la racine du projet
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

# 🔧 Initialisation Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "papex.settings.prod")
django.setup()

from api.leads.models import Lead
from api.lead_status.models import LeadStatus


def run():

    print("🚀 Création du lead de test...")

    status = LeadStatus.objects.get(code=RDV_A_CONFIRMER)

    lead = Lead.objects.create(
        first_name="Marc",
        last_name="Test",
        email="mtakoumba@gmail.com",
        phone="0759650005",
        status=status,
        appointment_date=timezone.now() + timezone.timedelta(days=3),
    )

    print(f"✅ Lead créé ID={lead.id}")

    LeadEvent.log(
        lead=lead,
        event_code="LEAD_CREATED",
        data={"source": "automation_test"}
    )

    print("📊 Event LEAD_CREATED enregistré")


if __name__ == "__main__":
    run()