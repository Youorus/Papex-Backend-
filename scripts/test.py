import os
import django

# 🔧 Init Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "papex.settings.prod")
django.setup()

from api.leads.models import Lead
from api.leads.constants import PRESENT, RDV_TELEPHONE, RDV_PRESENTIEL


def run():
    # 1️⃣ Tous les PRESENT
    present_count = Lead.objects.filter(
        status__code=PRESENT,
    appointment_type =RDV_PRESENTIEL
    ).count()

    # 2️⃣ PRESENT + TELEPHONE
    present_tel_count = Lead.objects.filter(
        status__code=PRESENT,
        appointment_type=RDV_TELEPHONE
    ).count()

    print("📊 Statistiques RDV")
    print("-------------------")
    print(f"👤 PRESENT total : {present_count}")
    print(f"📞 PRESENT téléphonique : {present_tel_count}")


if __name__ == "__main__":
    run()