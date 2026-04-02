from django.utils import timezone
from django.db import transaction

from api.leads.models import Lead
from api.leads_task.models import LeadTask
from api.leads_task_type.models import LeadTaskType
from api.users.models import User
from api.users.roles import UserRoles
from api.leads.constants import ABSENT


def create_absent_followup_tasks():
    """
    Crée des tâches de relance pour les leads ABSENTS.

    - Assignées aux utilisateurs ACCUEIL actifs
    - Évite les doublons (1 tâche / lead / jour)
    """

    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # 🔹 Récupération type de tâche
    task_type, _ = LeadTaskType.objects.get_or_create(
        code="RELANCE_ABSENT",
        defaults={
            "label": "Relance client absent",
            "description": "Relancer un client qui n'a pas honoré son rendez-vous",
        },
    )

    # 🔹 Users ACCUEIL actifs
    accueil_users = list(
        User.objects.filter(
            role=UserRoles.ACCUEIL,
            is_active=True,
        )
    )

    if not accueil_users:
        return "No active ACCUEIL users"

    # 🔹 Leads ABSENTS
    leads = Lead.objects.filter(
        status__code=ABSENT,
        appointment_date__isnull=False,
    )

    created_count = 0

    with transaction.atomic():
        for lead in leads:

            # 🔥 Anti doublon : tâche déjà créée aujourd'hui ?
            already_exists = LeadTask.objects.filter(
                lead=lead,
                task_type=task_type,
                created_at__gte=today_start,
            ).exists()

            if already_exists:
                continue

            # 🔥 Contenu clair
            title = f"Relancer {lead.first_name} {lead.last_name}"

            description = (
                f"Le client {lead.first_name} {lead.last_name} "
                f"n'était pas présent à son rendez-vous du "
                f"{lead.appointment_date.strftime('%d/%m/%Y à %H:%M')}.\n\n"
                f"👉 Action : recontacter le client pour reprogrammer un rendez-vous."
            )

            # 🔥 Création pour CHAQUE user accueil
            for user in accueil_users:
                LeadTask.objects.create(
                    lead=lead,
                    task_type=task_type,
                    title=title,
                    description=description,
                    due_at=now,  # tâche pour aujourd’hui
                    assigned_to=user,
                )
                created_count += 1

    return f"{created_count} tasks created"