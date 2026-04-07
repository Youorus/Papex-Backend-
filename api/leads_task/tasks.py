from datetime import timedelta
from itertools import cycle

from django.utils import timezone
from django.db import transaction

from api.leads.models import Lead
from api.leads_task.models import LeadTask
from api.leads_task_type.models import LeadTaskType
from api.users.models import User
from api.users.roles import UserRoles
from api.leads.constants import ABSENT
from api.leads_task.constants import LeadTaskStatus


def create_absent_followup_tasks(limit_per_user_per_day=20):
    """
    Crée des tâches de relance intelligentes pour les leads au statut ABSENT.

    Logique d'optimisation :
    1. **Anti-doublon** : Exclut les leads ayant déjà une tâche 'RELANCE_ABSENT' en cours (TODO).
    2. **Équité (Round-Robin)** : Distribue les leads un par un aux agents d'accueil actifs.
    3. **Lissage (Pacing)** : Limite à X tâches par jour et par agent pour éviter la surcharge.
    """
    now = timezone.now()

    # 1. Sécurité : Récupération du type de tâche
    task_type, _ = LeadTaskType.objects.get_or_create(
        code="RELANCE_ABSENT",
        defaults={
            "label": "Relance client absent",
            "description": "Contacter le client pour reprogrammer suite à son absence au RDV.",
        },
    )

    # 2. Identification des agents d'accueil disponibles
    accueil_users = list(
        User.objects.filter(
            role=UserRoles.ACCUEIL,
            is_active=True,
        )
    )

    if not accueil_users:
        return "Abandon : Aucun utilisateur ACCUEIL actif trouvé."

    # 3. Filtrage des leads à traiter (Performance optimisée)
    # On récupère les IDs des leads qui ont déjà une tâche de relance non terminée
    leads_with_active_tasks = LeadTask.objects.filter(
        task_type=task_type,
        status=LeadTaskStatus.TODO
    ).values_list('lead_id', flat=True)

    # On récupère uniquement les leads ABSENTS sans tâche active
    leads_to_process = Lead.objects.filter(
        status__code=ABSENT,
        appointment_date__isnull=False,
    ).exclude(id__in=leads_with_active_tasks).order_by('-appointment_date')

    if not leads_to_process.exists():
        return "Info : Aucun nouveau lead absent à planifier."

    # 4. Paramètres de distribution
    num_agents = len(accueil_users)
    user_pool = cycle(accueil_users)  # Alternance infinie entre les agents sélectionnés

    # Capacité de traitement totale de l'équipe par jour
    daily_capacity = num_agents * limit_per_user_per_day

    created_count = 0

    # 5. Création massive sécurisée
    with transaction.atomic():
        for index, lead in enumerate(leads_to_process):
            # Calcul du décalage (Pacing) :
            # Si index=45 et daily_capacity=40, days_offset=1 (planifié pour demain)
            days_offset = index // daily_capacity
            scheduled_date = now + timedelta(days=days_offset)

            # Sélection de l'agent suivant (Équité)
            assigned_user = next(user_pool)

            # Création de la tâche CRM
            LeadTask.objects.create(
                lead=lead,
                task_type=task_type,
                title=f"Relancer {lead.first_name} {lead.last_name}",
                description=(
                    f"Le client {lead.first_name} {lead.last_name} n'était pas présent "
                    f"à son rendez-vous du {lead.appointment_date.strftime('%d/%m/%Y à %H:%M')}.\n\n"
                    f"👉 Action : Recontacter pour reprogrammer un rendez-vous.\n"
                    f"📌 Affectation : {assigned_user.get_full_name()} (Vague J+{days_offset})"
                ),
                due_at=scheduled_date,
                assigned_to=assigned_user,
                status=LeadTaskStatus.TODO,
            )
            created_count += 1

    total_days = (created_count // daily_capacity) + 1
    return f"Succès : {created_count} tâches réparties sur {total_days} jours pour {num_agents} agents."