from django.core.management.base import BaseCommand
from django_celery_beat.models import PeriodicTask, CrontabSchedule


class Command(BaseCommand):
    help = "Initialise les schedulers Celery Beat (rappels RDV et absences)"

    def handle(self, *args, **options):

        # ============================================================
        # 🔔 RAPPEL RDV J-2 — Tous les jours à 09:00 (heure locale)
        # ============================================================
        reminder_schedule, _ = CrontabSchedule.objects.get_or_create(
            minute="0",
            hour="9",
            timezone="Europe/Paris",
        )

        PeriodicTask.objects.get_or_create(
            name="Rappel RDV J-2",
            defaults={
                "task": "api.leads.tasks.send_reminder_notifications",
                "crontab": reminder_schedule,
                "enabled": True,
            },
        )

        # ============================================================
        # 🚫 MARQUER RDV ABSENTS — Toutes les 30 minutes
        # ============================================================
        absent_schedule, _ = CrontabSchedule.objects.get_or_create(
            minute="*/30",
            timezone="Europe/Paris",
        )

        PeriodicTask.objects.get_or_create(
            name="Marquer RDV absents",
            defaults={
                "task": "api.leads.tasks.mark_absent_leads",
                "crontab": absent_schedule,
                "enabled": True,
            },
        )

        self.stdout.write(
            self.style.SUCCESS("✅ Celery Beat schedulers créés / vérifiés")
        )
