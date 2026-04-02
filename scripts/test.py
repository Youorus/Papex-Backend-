import os
import django

# 🔧 Initialisation Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "papex.settings.prod")
django.setup()

from api.lead_status.models import LeadStatus

print("\n📊 ===== LISTE DES STATUTS =====\n")

for status in LeadStatus.objects.all():
    print(f"Code: {status.code} | Label: {status.label}")

print("\n✅ Terminé\n")