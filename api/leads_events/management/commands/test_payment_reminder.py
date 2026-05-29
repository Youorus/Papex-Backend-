from django.core.management.base import BaseCommand
from api.contracts.models import Contract
from api.utils.communication.reminders import _run_send_payment_reminder

class Command(BaseCommand):
    help = "Envoie un email et un SMS de test pour le rappel de paiement."

    def add_arguments(self, parser):
        parser.add_argument("contract_id", type=int, help="ID du contrat pour le test")

    def handle(self, *args, **options):
        contract_id = options["contract_id"]
        self.stdout.write(f"🚀 Simulation d'un rappel de paiement pour le contrat #{contract_id}...")
        
        try:
            _run_send_payment_reminder(contract_id)
            self.stdout.write(self.style.SUCCESS("✅ Rappel envoyé !"))
            self.stdout.write("Vérifiez la boîte mail du client lié au contrat et son téléphone.")
        except Contract.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"❌ Contrat #{contract_id} introuvable."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Erreur : {str(e)}"))
