from datetime import timedelta

from django.db import transaction, IntegrityError
from django.utils import timezone

from api.leads.constants import ABSENT
from api.leads.models import Lead
from api.leads_task.constants import LeadTaskStatus
from api.leads_task.models import LeadTask
from api.leads_task_type.models import LeadTaskType
from api.users.models import User
from api.users.roles import UserRoles


EMMA_EMAIL = "emma.jacquin@papiers-express.fr"
RELANCE_ABSENT_CODE = "RELANCE_ABSENT"


def get_emma_accueil_user():
    return User.objects.get(
        email=EMMA_EMAIL,
        role=UserRoles.ACCUEIL,
        is_active=True,
    )


def get_relance_absent_task_type():
    task_type, _ = LeadTaskType.objects.get_or_create(
        code=RELANCE_ABSENT_CODE,
        defaults={
            "label": "Relance client absent",
            "description": "Contacter le client pour reprogrammer suite à son absence au RDV.",
        },
    )
    return task_type


def create_absent_followup_tasks(limit_per_user_per_day=20):
    """
    Crée des tâches de relance pour les leads ABSENT.

    Règles :
    - Toutes les tâches ABSENT sont assignées à Emma.
    - Une seule tâche TODO par lead + type de tâche.
    - Si une tâche existe déjà, elle n'est pas recréée.
    - Les tâches sont réparties sur plusieurs jours selon la limite journalière.
    """
    now = timezone.now()
    daily_capacity = max(int(limit_per_user_per_day), 1)

    try:
        assigned_user = get_emma_accueil_user()
    except User.DoesNotExist:
        return f"Abandon : Emma introuvable ou inactive avec l'email {EMMA_EMAIL}."

    task_type = get_relance_absent_task_type()

    leads_with_active_tasks = LeadTask.objects.filter(
        task_type=task_type,
        status=LeadTaskStatus.TODO,
    ).values_list("lead_id", flat=True)

    leads_to_process = (
        Lead.objects.filter(
            status__code=ABSENT,
            appointment_date__isnull=False,
        )
        .exclude(id__in=leads_with_active_tasks)
        .order_by("-appointment_date")
    )

    if not leads_to_process.exists():
        return "Info : Aucun nouveau lead absent à planifier."

    created_count = 0
    skipped_count = 0

    with transaction.atomic():
        for index, lead in enumerate(leads_to_process):
            days_offset = index // daily_capacity
            scheduled_date = now + timedelta(days=days_offset)

            appointment_label = (
                lead.appointment_date.strftime("%d/%m/%Y à %H:%M")
                if lead.appointment_date
                else "date inconnue"
            )

            title = f"Relancer {lead.first_name} {lead.last_name}"
            description = (
                f"Le client {lead.first_name} {lead.last_name} n'était pas présent "
                f"à son rendez-vous du {appointment_label}.\n\n"
                f"👉 Action : Recontacter pour reprogrammer un rendez-vous.\n"
            )

            existing_task = LeadTask.objects.filter(
                lead=lead,
                task_type=task_type,
                status=LeadTaskStatus.TODO,
            ).first()

            if existing_task:
                skipped_count += 1
                continue

            try:
                LeadTask.objects.create(
                    lead=lead,
                    task_type=task_type,
                    title=title,
                    description=description,
                    due_at=scheduled_date,
                    assigned_to=assigned_user,
                    status=LeadTaskStatus.TODO,
                )
                created_count += 1

            except IntegrityError:
                skipped_count += 1

    total_days = ((created_count - 1) // daily_capacity) + 1 if created_count else 0

    return (
        f"Succès : {created_count} tâche(s) ABSENT créée(s), "
        f"{skipped_count} doublon(s) ignoré(s), "
        f"assignée(s) à {assigned_user.get_full_name()} "
        f"et répartie(s) sur {total_days} jour(s)."
    )