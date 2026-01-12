from datetime import date

from django.core.management.base import BaseCommand
from django.utils import timezone

from api.leads.constants import RDV_A_CONFIRMER, RDV_CONFIRME
from api.leads.models import Lead
from api.utils.email.leads.tasks import send_appointment_confirmation_task
from api.sms.tasks import send_appointment_confirmation_sms_task


class Command(BaseCommand):
    help = (
        "Rattrapage : renvoie les notifications de confirmation "
        "pour les leads créés aujourd’hui (RDV_A_CONFIRMER / RDV_CONFIRME)."
    )

    def handle(self, *args, **options):
        today = timezone.localdate()

        leads = Lead.objects.filter(
            created_at__date=today,
            status__code__in=[RDV_A_CONFIRMER, RDV_CONFIRME],
        )

        total = leads.count()
        self.stdout.write(f"🔎 {total} lead(s) trouvé(s)")

        sent_email = 0
        sent_sms = 0

        for lead in leads:
            self.stdout.write(f"➡️ Lead #{lead.id}")

            # 📧 EMAIL
            if lead.email:
                send_appointment_confirmation_task.delay(lead.id)
                sent_email += 1
                self.stdout.write("   📧 Email programmé")
            else:
                self.stdout.write("   ℹ️ Pas d’email")

            # 📲 SMS
            if lead.phone:
                send_appointment_confirmation_sms_task.delay(lead.id)
                sent_sms += 1
                self.stdout.write("   📲 SMS programmé")
            else:
                self.stdout.write("   ℹ️ Pas de téléphone")

        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Terminé — Emails: {sent_email} | SMS: {sent_sms}"
            )
        )