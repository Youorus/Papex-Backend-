import os
import django
from django.utils import timezone

# 🔧 Initialisation Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "papex.settings.prod")
django.setup()

from api.leads.models import Lead
from api.leads.constants import RDV_VISIO_CONFERENCE, ANNULE, PRESENT
from api.utils.email.leads.notifications import send_visio_payment_email

def run_mass_visio_payment_emails():
    print("🔎 Recherche des leads avec RDV Visio programmés...")
    
    now = timezone.now()
    
    # On cherche les leads :
    # 1. Type de RDV = Visio
    # 2. Date de RDV dans le futur
    # 3. Email renseigné
    # 4. Non annulés et non déjà présents
    leads = Lead.objects.filter(
        appointment_type=RDV_VISIO_CONFERENCE,
        appointment_date__gte=now,
        email__isnull=False,
    ).exclude(
        status__code__in=[ANNULE, PRESENT]
    ).exclude(
        email=""
    )
    
    total = leads.count()
    print(f"📊 {total} lead(s) éligible(s) trouvé(s).")
    
    success_count = 0
    error_count = 0
    skipped_count = 0
    
    report = []
    
    for lead in leads:
        print(f"📧 Envoi à {lead.first_name} {lead.last_name} ({lead.email})...")
        try:
            # On vérifie si on n'a pas déjà envoyé un mail de paiement visio aujourd'hui
            # pour éviter le spam si on relance le script
            from api.leads_events.models import LeadEvent
            already_sent = LeadEvent.objects.filter(
                lead=lead,
                event_type__code="VISIO_PAYMENT_SENT", # On va logger cet event spécifique
                occurred_at__date=now.date()
            ).exists()
            
            if already_sent:
                print(f"⏩ Déjà envoyé aujourd'hui pour #{lead.id}, skip.")
                skipped_count += 1
                continue

            send_visio_payment_email(lead)
            
            # Log l'événement spécifique pour le suivi
            LeadEvent.log(
                lead=lead,
                event_code="VISIO_PAYMENT_SENT",
                actor=None,
                data={"email": lead.email, "batch_run": True}
            )
            
            success_count += 1
            report.append(f"✅ SUCCÈS : {lead.first_name} {lead.last_name} (#{lead.id})")
        except Exception as e:
            error_count += 1
            print(f"❌ Erreur pour #{lead.id} : {e}")
            report.append(f"❌ ERREUR : {lead.first_name} {lead.last_name} (#{lead.id}) - {str(e)}")

    print("\n" + "="*30)
    print("      RAPPORT FINAL")
    print("="*30)
    print(f"Total éligibles : {total}")
    print(f"Succès          : {success_count}")
    print(f"Skippés         : {skipped_count}")
    print(f"Erreurs         : {error_count}")
    print("="*30)
    
    if report:
        print("\nDétails :")
        for line in report:
            print(line)

if __name__ == "__main__":
    run_mass_visio_payment_emails()
