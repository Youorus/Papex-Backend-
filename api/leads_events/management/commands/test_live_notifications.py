from django.core.management.base import BaseCommand
from api.leads.models import Lead
from api.contracts.models import Contract
from api.utils.communication.dispatcher import CommunicationDispatcher
from api.utils.email.internal_alerts import send_ai_escalation_alert
from decimal import Decimal

class Command(BaseCommand):
    help = "Envoie des notifications de test réelles aux numéros et emails spécifiés."

    def handle(self, *args, **options):
        phones = ["+33603586704", "+33759650005"]
        emails = ["marc.takoumba@papiers-express.fr", "themenain.bamba@papiers-express.fr"]
        
        self.stdout.write("🚀 Démarrage du test LIVE général...")

        # 1. TEST ESCALADE (Kemia)
        self.stdout.write("--- 1. Test Escalade Kemia ---")
        # On prend un lead bidon pour le contexte
        lead = Lead.objects.first()
        reason = "Ceci est un test de validation finale pour Kemia. Tout semble parfaitement opérationnel !"
        
        for email in emails:
            # Note: send_ai_escalation_alert a ses propres destinataires hardcodés, 
            # mais ici on veut tester le template et l'envoi.
            pass
        
        # On utilise directement la fonction d'alerte (qui envoie aux deux emails)
        send_ai_escalation_alert(lead=lead, reason=reason, sender_phone=phones[0])
        self.stdout.write(self.style.SUCCESS("✅ Alertes escalade Kemia envoyées aux emails."))

        # 2. TEST RAPPEL PAIEMENT (Dispatcher + SMS + Email)
        self.stdout.write("\n--- 2. Test Rappel Paiement ---")
        
        # On crée un contexte de test
        mock_context = {
            "balance": "450.00",
            "due_date": "05/06/2026",
            "client_name": "Marc/Themenain"
        }
        sms_text = "Bonjour, c'est Papiers Express. Petit rappel amical pour votre echeance de 450.00 EUR prevue le 05/06. A bientot !"
        subject = "Rappel amical : votre échéance Papiers Express"

        # On "triche" un peu pour envoyer aux bons endroits sans modifier la DB
        class MockLead:
            def __init__(self, id, email, phone, first_name):
                self.id = id
                self.email = email
                self.phone = phone
                self.first_name = first_name

        for i, email in enumerate(emails):
            phone = phones[i] if i < len(phones) else phones[0]
            mock_lead = MockLead(id=999, email=email, phone=phone, first_name="Test")
            
            self.stdout.write(f"Envoi rappel vers {email} et {phone}...")
            
            CommunicationDispatcher.send_notification(
                lead=mock_lead,
                subject=subject,
                template_prefix="payments/reminder",
                context=mock_context,
                sms_body=sms_text,
                force_both=True
            )
            
        self.stdout.write(self.style.SUCCESS("✅ Rappels de paiement envoyés aux numéros et emails spécifiés !"))
