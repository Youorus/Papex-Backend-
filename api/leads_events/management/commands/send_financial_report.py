from django.core.management.base import BaseCommand
from api.utils.communication.reminders import send_financial_status_report

class Command(BaseCommand):
    help = "Génère et envoie le rapport financier des encours par email."

    def handle(self, *args, **options):
        self.stdout.write("🚀 Génération du rapport financier en cours...")
        success = send_financial_status_report()
        if success:
            self.stdout.write(self.style.SUCCESS("✅ Rapport envoyé avec succès à Marc et Themenain !"))
        else:
            self.stdout.write(self.style.ERROR("❌ Échec de la génération ou de l'envoi du rapport."))
