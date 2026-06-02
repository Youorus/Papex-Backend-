import os
import sys
import django
from django.utils import timezone

# Add the project root to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Configure Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "papex.settings.prod")
django.setup()

from api.leads.models import Lead
from api.utils.email.leads.tasks import send_visio_payment_task

def send_pending_visio_payments():
    """
    Identifie tous les rendez-vous en visio à venir et envoie l'e-mail de paiement.
    """
    now = timezone.now()
    
    # On cherche les leads qui ont :
    # 1. Un rendez-vous dans le futur.
    # 2. Le type de rendez-vous est "VISIO_CONFERENCE".
    # 3. Un email valide.
    upcoming_visio_leads = Lead.objects.filter(
        appointment_date__gte=now,
        appointment_type="VISIO_CONFERENCE",
        email__isnull=False
    ).exclude(email__exact='')

    if not upcoming_visio_leads.exists():
        print("✅ Aucun rendez-vous en visio à venir nécessitant un e-mail de paiement.")
        return

    print(f"📧 Trouvé {upcoming_visio_leads.count()} rendez-vous en visio à venir. Envoi des e-mails de paiement...")

    count = 0
    for lead in upcoming_visio_leads:
        try:
            print(f"  -> Envoi pour le lead #{lead.id} ({lead.first_name} {lead.last_name}) à {lead.email}...")
            send_visio_payment_task(lead.id)
            count += 1
        except Exception as e:
            print(f"  ❌ Erreur lors de l'envoi pour le lead #{lead.id}: {e}")

    print(f"✅ Terminé. {count} e-mails de paiement ont été mis en file d'attente pour envoi.")

if __name__ == "__main__":
    send_pending_visio_payments()
