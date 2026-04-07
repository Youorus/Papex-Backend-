import os
import sys
import django
from datetime import timedelta
from itertools import cycle

# 1. 🔧 Configuration de l'environnement Django
sys.path.append(os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "papex.settings.prod")
django.setup()

from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from api.leads.models import Lead
from api.leads_task.models import LeadTask
from api.leads_task_type.models import LeadTaskType
from api.users.models import User
from api.users.roles import UserRoles
from api.leads.constants import ABSENT
from api.leads_task.constants import LeadTaskStatus

# 🎯 Cible pour la réassignation
USER_EMAIL_A_REPLACER = "test@papex.fr"


def cleanup_duplicates():
    """Supprime les doublons pour nettoyer la base avant la nouvelle répartition."""
    print("\n--- 🧹 NETTOYAGE DES DOUBLONS ---")
    target_type = LeadTaskType.objects.filter(code="RELANCE_ABSENT").first()
    if not target_type:
        print("ℹ️ Aucun type RELANCE_ABSENT trouvé. Nettoyage ignoré.")
        return

    duplicate_leads = (
        LeadTask.objects.filter(task_type=target_type, status=LeadTaskStatus.TODO)
        .values('lead')
        .annotate(cnt=Count('id'))
        .filter(cnt__gt=1)
    )

    deleted = 0
    with transaction.atomic():
        for entry in duplicate_leads:
            tasks = list(LeadTask.objects.filter(
                lead_id=entry['lead'],
                task_type=target_type,
                status=LeadTaskStatus.TODO
            ).order_by('-created_at'))
            # On garde le plus récent, on supprime les autres
            for t in tasks[1:]:
                t.delete()
                deleted += 1
    print(f"✅ Nettoyage terminé : {deleted} tâches inutiles supprimées.")


def get_active_accueil_users():
    """Récupère les utilisateurs ACCUEIL actifs en EXCLUANT l'utilisateur cible."""
    print("\n--- 👥 SÉLECTION DES AGENTS D'ACCUEIL ---")

    # Exclusion automatique de l'utilisateur dont on veut réassigner les leads
    users = list(User.objects.filter(
        role=UserRoles.ACCUEIL,
        is_active=True
    ).exclude(email=USER_EMAIL_A_REPLACER))

    if not users:
        print(f"❌ Erreur : Aucun autre utilisateur 'ACCUEIL' actif trouvé (hors {USER_EMAIL_A_REPLACER}).")
        sys.exit(1)

    for i, u in enumerate(users):
        print(f"[{i}] {u.get_full_name()} (ID: {u.id})")

    print(f"\n💡 Note : {USER_EMAIL_A_REPLACER} est automatiquement exclu de la liste.")
    print("- Tape 'all' pour sélectionner tous les autres agents.")
    print("- Tape les numéros séparés par des virgules (ex: 0,2) pour choisir des personnes précises.")

    selection = input("\nVotre choix : ").strip()

    if selection.lower() == 'all':
        return users

    try:
        indices = [int(x.strip()) for x in selection.split(",")]
        selected = [users[i] for i in indices]
        return selected
    except (ValueError, IndexError):
        print("❌ Sélection invalide. Script arrêté.")
        sys.exit(1)


def run_smart_scheduler(selected_users, tasks_per_agent_per_day=20):
    """
    Planification intelligente :
    1. Libère les leads de l'utilisateur à remplacer.
    2. Redistribue tout le flux aux agents sélectionnés sur plusieurs jours.
    """
    print(f"\n--- 📅 PLANIFICATION (Limite : {tasks_per_agent_per_day} tâches/agent/jour) ---")

    task_type, _ = LeadTaskType.objects.get_or_create(
        code="RELANCE_ABSENT",
        defaults={
            "label": "Relance client absent",
            "description": "Tâche automatique pour recontacter un client absent au RDV."
        }
    )

    with transaction.atomic():
        # 🔥 ÉTAPE CLÉ : On libère les leads de test@papex.fr
        print(f"🔄 Libération des leads actuellement assignés à {USER_EMAIL_A_REPLACER}...")
        deleted_count = LeadTask.objects.filter(
            assigned_to__email=USER_EMAIL_A_REPLACER,
            task_type=task_type,
            status=LeadTaskStatus.TODO
        ).delete()[0]
        print(f"✅ {deleted_count} relances ont été remises dans la file d'attente pour redistribution.")

        # 1. On liste les leads qui ont déjà une relance chez les AUTRES agents (pour éviter les doublons)
        leads_already_assigned = LeadTask.objects.filter(
            task_type=task_type,
            status=LeadTaskStatus.TODO
        ).values_list('lead_id', flat=True)

        # 2. On récupère les leads ABSENTS sans tâche active (incluant ceux qu'on vient de libérer)
        leads_to_process = Lead.objects.filter(
            status__code=ABSENT,
            appointment_date__isnull=False
        ).exclude(id__in=leads_already_assigned).order_by('appointment_date')

        total_leads = leads_to_process.count()
        if total_leads == 0:
            print("ℹ️ Aucun lead absent ne nécessite de nouvelle tâche.")
            return

        num_agents = len(selected_users)
        daily_group_capacity = num_agents * tasks_per_agent_per_day

        user_pool = cycle(selected_users)
        now = timezone.now()
        created_count = 0

        print(f"Analyse : {total_leads} leads à répartir sur {num_agents} agent(s).")

        for index, lead in enumerate(leads_to_process):
            # Calcul du décalage pour l'échéance (Pacing)
            days_to_add = index // daily_group_capacity
            scheduled_date = now + timedelta(days=days_to_add)

            current_agent = next(user_pool)

            LeadTask.objects.create(
                lead=lead,
                task_type=task_type,
                title=f"Relance Absent : {lead.first_name} {lead.last_name}",
                description=(
                    f"Le client ne s'est pas présenté le {lead.appointment_date.strftime('%d/%m/%Y')}.\n"
                    f"Assigné à {current_agent.get_full_name()} suite à réassignation (Vague J+{days_to_add})."
                ),
                due_at=scheduled_date,
                assigned_to=current_agent,
                status=LeadTaskStatus.TODO
            )
            created_count += 1

    total_days = (total_leads // daily_group_capacity) + 1
    print(f"✅ Succès : {created_count} tâches créées/réassignées.")
    print(f"📊 Charge répartie sur {total_days} jour(s).")


if __name__ == "__main__":
    print(f"--- GESTIONNAIRE DE RELANCES ABSENTS (Version 2026) ---")

    # Étape 1 : Nettoyage des doublons globaux
    cleanup_duplicates()

    # Étape 2 : Choix des agents (excluant test@papex.fr)
    agents = get_active_accueil_users()
    print(f"Agents retenus : {[a.get_full_name() for a in agents]}")

    # Étape 3 : Redistribution et planification
    run_smart_scheduler(agents, tasks_per_agent_per_day=20)

    print("\nFin du traitement.")