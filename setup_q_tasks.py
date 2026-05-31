
import os
import django
from django.utils import timezone
from datetime import time

# Configuration de l'environnement Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'papex.settings.prod')
django.setup()

from django_q.models import Schedule

def setup_tasks():
    print("🚀 Configuration automatique des tâches Django Q...")

    # Définition des tâches à planifier
    tasks = [
        {
            "name": "Envoi des Rappels de RDV (24h/48h)",
            "func": "api.leads.tasks.send_appointment_reminders",
            "schedule_type": Schedule.MINUTES,
            "minutes": 5,
            "repeats": -1,
        },
        {
            "name": "Marquage des Leads Absents",
            "func": "api.leads.tasks.mark_missed_appointments_as_absent",
            "schedule_type": Schedule.HOURLY,
            "repeats": -1,
        },
        {
            "name": "Génération des tâches CRM (Relance Absents)",
            "func": "api.leads_task.tasks.create_absent_followup_tasks",
            "schedule_type": Schedule.HOURLY,
            "repeats": -1,
        },
        {
            "name": "Rapport Journalier (Activité Leads)",
            "func": "api.leads.tasks.send_daily_report",
            "schedule_type": Schedule.DAILY,
            "repeats": -1,
            "hour": 20,
            "minute": 0,
        },
        {
            "name": "Rappels de Paiement (J-7)",
            "func": "api.utils.communication.reminders.run_payment_reminders",
            "schedule_type": Schedule.DAILY,
            "repeats": -1,
            "hour": 9,
            "minute": 0,
        },
        {
            "name": "Rapport Financier Quotidien (Encours)",
            "func": "api.utils.communication.reminders.send_financial_status_report",
            "schedule_type": Schedule.DAILY,
            "repeats": -1,
            "hour": 8,
            "minute": 30,
        },
    ]

    for t in tasks:
        # Calculer le prochain lancement pour les tâches quotidiennes
        next_run = timezone.now()
        if t["schedule_type"] == Schedule.DAILY:
            target_time = time(t.get("hour", 0), t.get("minute", 0))
            next_run = timezone.now().replace(
                hour=target_time.hour, 
                minute=target_time.minute, 
                second=0, 
                microsecond=0
            )
            # Si l'heure est déjà passée aujourd'hui, on passe à demain
            if next_run < timezone.now():
                next_run += timezone.timedelta(days=1)

        # Création ou mise à jour
        obj, created = Schedule.objects.update_or_create(
            func=t["func"],
            defaults={
                "name": t["name"],
                "schedule_type": t["schedule_type"],
                "minutes": t.get("minutes"),
                "repeats": t["repeats"],
                "next_run": next_run,
            }
        )

        status = "Créée ✨" if created else "Mise à jour ✅"
        print(f"  [{status}] {t['name']} -> {t['func']} (Prochain run: {obj.next_run})")

    print("\n✅ Toutes les tâches critiques sont configurées et prêtes pour la production.")

if __name__ == "__main__":
    setup_tasks()
