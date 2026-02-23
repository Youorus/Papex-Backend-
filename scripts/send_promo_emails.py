import os
import csv
import django

# =========================
# INIT DJANGO
# =========================
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "papex.settings.prod")
django.setup()

from django.utils import timezone
from api.leads.models import Lead
from api.utils.email import send_html_email


# =========================
# CONFIG EMAIL
# =========================

SUBJECT = "🚨 Dossier bloqué en préfecture ? Voici comment débloquer la situation"
TEMPLATE = "email/promo/promo_email.html"

SOURCE = "db"  # "csv" ou "db"
CSV_PATH = "emails.csv"


# =========================
# MODE TEST
# =========================

TEST_MODE = True
TEST_EMAIL = "themenain.bamba@papiers-express.fr"


# =========================
# CONTEXTE TEMPLATE
# =========================

def build_context(lead=None):
    return {
        "year": timezone.now().year,
        "user": lead,  # permet {{ user.first_name }}
    }


# =========================
# CSV
# =========================

def get_leads_from_csv(path):
    leads = []

    try:
        with open(path, newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                email = row.get("email")
                first_name = row.get("first_name", "")

                if email:
                    leads.append({"email": email.strip(), "first_name": first_name})

    except FileNotFoundError:
        print(f"❌ CSV introuvable : {path}")

    return leads


# =========================
# DATABASE
# =========================

def get_leads_from_db():
    return Lead.objects.exclude(email__isnull=True).exclude(email__exact="")


# =========================
# ENVOI TEST
# =========================

def send_test_email():
    context = build_context()

    send_html_email(
        to_email=TEST_EMAIL,
        subject=SUBJECT,
        template_name=TEMPLATE,
        context=context,
    )

    print(f"🧪 Email test envoyé à {TEST_EMAIL}")


# =========================
# ENVOI MASSIF
# =========================

def run():
    if TEST_MODE:
        print("🧪 MODE TEST ACTIVÉ")
        send_test_email()
        return

    if SOURCE == "csv":
        leads = get_leads_from_csv(CSV_PATH)
    else:
        leads = get_leads_from_db()

    if not leads:
        print("⚠️ Aucun email trouvé")
        return

    print(f"📨 {len(leads)} emails à envoyer")

    success = 0
    errors = 0

    for lead in leads:
        try:
            if SOURCE == "csv":
                email = lead["email"]
                context = build_context()
            else:
                email = lead.email
                context = build_context(lead)

            send_html_email(
                to_email=email,
                subject=SUBJECT,
                template_name=TEMPLATE,
                context=context,
            )

            print(f"✅ Envoyé : {email}")
            success += 1

        except Exception as e:
            print(f"❌ Erreur pour {email} → {e}")
            errors += 1

    print("\n📊 Résumé")
    print(f"✅ Succès : {success}")
    print(f"❌ Erreurs : {errors}")


# =========================
# ENTRYPOINT
# =========================

if __name__ == "__main__":
    run()