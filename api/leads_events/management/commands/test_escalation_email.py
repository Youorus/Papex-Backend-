from django.core.management.base import BaseCommand
from api.leads.models import Lead
from api.utils.email.internal_alerts import send_ai_escalation_alert

class Command(BaseCommand):
    help = "Envoie un email de test pour l'escalade IA (Alerte Marc & Themenain)."

    def handle(self, *args, **options):
        self.stdout.write("🚀 Préparation de l'email de test...")
        
        # On essaie de prendre un lead existant ou on crée un faux contexte
        lead = Lead.objects.first()
        reason = "Ceci est un TEST de l'escalade IA. Situation : Client demande un avocat en urgence pour une procédure OQTF complexe."
        phone = "33612345678"
        
        self.stdout.write(f"📧 Envoi de l'alerte pour le lead : {lead.first_name if lead else 'Test User'}")
        
        try:
            send_ai_escalation_alert(
                lead=lead,
                reason=reason,
                sender_phone=phone
            )
            self.stdout.write(self.style.SUCCESS("✅ Email de test envoyé avec succès aux destinataires !"))
            self.stdout.write("Vérifiez vos boîtes mail (marc.takoumba@papiers-express.fr et themenain.bamba@papiers-express.fr).")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Échec de l'envoi : {str(e)}"))
