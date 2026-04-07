import os
import sys
import django

# 1. 🔧 Configuration de l'environnement Django
# On s'assure que le dossier courant est dans le chemin Python pour trouver 'api'
sys.path.append(os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "papex.settings.prod")
django.setup()

# 2. 📦 Imports Django (doivent être après django.setup())
from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from itertools import cycle

from api.leads.models import Lead
from api.leads_task.models import LeadTask
from api.leads_task_type.models import LeadTaskType
from api.users.models import User
from api.users.roles import UserRoles
from api.leads.constants import ABSENT
from api.leads_task.constants import LeadTaskStatus


def cleanup_relance_absent_duplicates():
    """
    Supprime les doublons de 'RELANCE_ABSENT' tous utilisateurs confondus.
    Ne garde que la tâche la plus récente par Lead.
    """
    print("--- 🧹 Début du nettoyage des doublons ---")

    try:
        target_type = LeadTaskType.objects.get(code="RELANCE_ABSENT")
    except LeadTaskType.DoesNotExist:
        return "⚠️ Type RELANCE_ABSENT inexistant. Rien à nettoyer."

    # On identifie les leads qui ont plusieurs tâches TODO pour ce type
    duplicate_leads = (
        LeadTask.objects.filter(task_type=target_type, status=LeadTaskStatus.TODO)
        .values('lead')
        .annotate(cnt=Count('id'))
        .filter(cnt__gt=1)
    )

    deleted_count = 0
    with transaction.atomic():
        for entry in duplicate_leads:
            lead_id = entry['lead']
            # On récupère toutes les tâches TODO de ce lead (triées par date décroissante)
            tasks = list(
                LeadTask.objects.filter(
                    lead_id=lead_id,
                    task_type=target_type,
                    status=LeadTaskStatus.TODO
                ).order_by('-created_at')
            )

            # On garde la première (index 0), on supprime les autres
            to_delete = tasks[1:]
            for t in to_delete:
                t.delete()
                deleted_count += 1

    return f"✅ Nettoyage terminé : {deleted_count} doublons supprimés."


def create_daily_absent_tasks(limit=20):
    """
    Crée les nouvelles tâches RELANCE_ABSENT.
    - Max 20 par exécution
    - Distribution Round-Robin (un par un) aux agents d'accueil
    - Vérifie l'existence avant création
    """
    print(f"--- 🚀 Création des tâches (Limite: {limit}) ---")

    # Récupération du type de tâche
    task_type, _ = LeadTaskType.objects.get_or_create(
        code="RELANCE_ABSENT",
        defaults={
            "label": "Relance client absent",
            "description": "Relancer un client qui n'a pas honoré son RDV",
        },
    )

    # Utilisateurs ACCUEIL actifs
    accueil_users = list(User.objects.filter(role=UserRoles.ACCUEIL, is_active=True))
    if not accueil_users:
        return "❌ Erreur : Aucun utilisateur ACCUEIL actif."

    # Préparation de la distribution circulaire
    user_cycle = cycle(accueil_users)

    # On identifie les leads qui ont DÉJÀ une tâche active (pour ne pas doubler)
    leads_with_tasks = LeadTask.objects.filter(
        task_type=task_type,
        status=LeadTaskStatus.TODO
    ).values_list('lead_id', flat=True)

    # Sélection des leads ABSENTS sans tâche active
    leads_to_process = Lead.objects.filter(
        status__code=ABSENT,
        appointment_date__isnull=False
    ).exclude(
        id__in=leads_with_tasks
    ).order_by('-appointment_date')[:limit]

    created_count = 0
    with transaction.atomic():
        for lead in leads_to_process:
            assigned_user = next(user_cycle)

            LeadTask.objects.create(
                lead=lead,
                task_type=task_type,
                title=f"Relance Absent : {lead.first_name} {lead.last_name}",
                description=(
                    f"Le client {lead.first_name} {lead.last_name} était absent au RDV "
                    f"du {lead.appointment_date.strftime('%d/%m/%Y à %H:%M')}."
                ),
                due_at=timezone.now(),
                assigned_to=assigned_user,
                status=LeadTaskStatus.TODO
            )
            created_count += 1

    return f"✅ Création terminée : {created_count} tâches créées et réparties."


if __name__ == "__main__":
    print(f"Démarrage du script - {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 1. Nettoyer les erreurs du passé
    result_clean = cleanup_relance_absent_duplicates()
    print(result_clean)

    # 2. Créer les nouvelles tâches proprement
    result_create = create_daily_absent_tasks(limit=20)
    print(result_create)

    print("Fin du traitement.")