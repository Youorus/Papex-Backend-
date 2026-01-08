import os
import django

# ============================================================
# 🔧 INITIALISATION DJANGO (PRODUCTION)
# ============================================================
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "papex.settings.prod")
django.setup()

# ============================================================
# 🧪 IMPORTS
# ============================================================
from datetime import timedelta
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from api.leads.views import LeadViewSet
from api.lead_status.models import LeadStatus
from api.leads.constants import RDV_CONFIRME
from api.users.models import User
from api.leads.models import Lead

# ============================================================
# 🧪 CONTEXTE DE TEST
# ============================================================
print("\n🧪 TEST CREATE LEAD VIA LeadViewSet.create()\n")

# Utilisateur réel (CONSEILLER ou ADMIN)
user = User.objects.filter(is_active=True).first()

if not user:
    raise Exception("❌ Aucun utilisateur actif trouvé")

print(f"👤 Utilisateur utilisé : {user.email}")

# ============================================================
# 🧪 PAYLOAD IDENTIQUE AU FRONT
# ⚠️ FORMAT DATE OBLIGATOIRE : DD/MM/YYYY HH:MM
# ============================================================
now = timezone.now()
appointment_date = (now + timedelta(days=1)).strftime("%d/%m/%Y %H:%M")

payload = {
    "first_name": "Test",
    "last_name": "ViewSet",
    "email": "mtakoumba@gmail.com",
    "phone": "+33759650005",
    "appointment_date": appointment_date,
}

# ============================================================
# 🧪 SETUP DRF
# ============================================================
factory = APIRequestFactory()
request = factory.post("/api/leads/", payload, format="json")
force_authenticate(request, user=user)

view = LeadViewSet.as_view({"post": "create"})
response = view(request)

# ============================================================
# 🧪 RÉSULTAT API
# ============================================================
print("📡 Status HTTP :", response.status_code)

if response.status_code != 201:
    print("❌ Erreur API :", response.data)
    raise SystemExit(1)

lead_id = response.data["id"]
print(f"✅ Lead créé avec succès (id={lead_id})")

# ============================================================
# 🧪 VÉRIFICATIONS MÉTIER (SANS ASSERT)
# ============================================================
lead = Lead.objects.get(id=lead_id)

print("\n🔍 VÉRIFICATIONS LEAD")
print("• Nom :", lead.first_name, lead.last_name)
print("• Email :", lead.email)
print("• Téléphone :", lead.phone)
print("• RDV :", lead.appointment_date)
print("• Statut :", lead.status.code if lead.status else None)
print("• last_reminder_sent :", lead.last_reminder_sent)

# Statut attendu
expected_status = LeadStatus.objects.get(code=RDV_CONFIRME).id
print("• Statut attendu :", RDV_CONFIRME)

if lead.status_id != expected_status:
    print("⚠️ ATTENTION : statut inattendu")

# ============================================================
# 🧪 FIN
# ============================================================
print("\n🎉 TEST CREATE LEAD VIA VIEWSET TERMINÉ AVEC SUCCÈS\n")