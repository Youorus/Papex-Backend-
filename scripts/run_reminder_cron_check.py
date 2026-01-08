import os
import django

# ============================================================
# 🔧 INITIALISATION DJANGO (PRODUCTION)
# ============================================================
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "papex.settings.prod")
django.setup()

# ============================================================
# 🧪 TEST SMTP DIRECT (ISOLÉ)
# ============================================================
from django.core.mail import send_mail
from django.conf import settings

print("\n🧪 TEST SMTP DIRECT (PRODUCTION)\n")

print("EMAIL_BACKEND =", settings.EMAIL_BACKEND)
print("EMAIL_HOST =", settings.EMAIL_HOST)
print("EMAIL_PORT =", settings.EMAIL_PORT)
print("EMAIL_USE_TLS =", settings.EMAIL_USE_TLS)
print("EMAIL_HOST_USER =", settings.EMAIL_HOST_USER)
print("DEFAULT_FROM_EMAIL =", settings.DEFAULT_FROM_EMAIL)

try:
    send_mail(
        subject="🧪 Test SMTP Papex PROD",
        message="Si tu reçois cet email, le SMTP fonctionne correctement ✅",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=["contact@papiers-express.fr"],  # mets ton email si besoin
        fail_silently=False,
    )
    print("\n✅ SMTP OK — email envoyé avec succès\n")
except Exception as e:
    print("\n❌ SMTP KO — erreur détectée")
    print(type(e).__name__, e)
    print("\n⛔ ARRÊT DU SCRIPT (SMTP NON FONCTIONNEL)\n")
    exit(1)

# ============================================================
# 🧪 TEST RAPPEL J-1 (LOGIQUE MÉTIER)
# ============================================================
from datetime import timedelta
from django.utils import timezone

from api.leads.tasks import send_reminder_emails
from api.leads.models import Lead
from api.lead_status.models import LeadStatus
from api.leads.constants import RDV_CONFIRME

print("🧪 TEST RAPPEL J-1 EN PROD DB\n")

now = timezone.now()
tomorrow = now + timedelta(days=1)

status = LeadStatus.objects.get(code=RDV_CONFIRME)

lead = Lead.objects.create(
    first_name="Test",
    last_name="Prod",
    email="mtakoumba@gmail.com",
    phone="+33759650005",
    appointment_date=tomorrow,
    status=status,
    last_reminder_sent=None,
)

print(f"✅ Lead créé id={lead.id}")

# 🔥 Appel direct de la logique métier
send_reminder_emails()

lead.refresh_from_db()

print("📬 last_reminder_sent =", lead.last_reminder_sent)
print("\n🎉 FIN DU TEST COMPLET\n")