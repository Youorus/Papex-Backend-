import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "papex.settings.prod")
django.setup()

from django.db import transaction
from django.db.models import Count

from api.leads.constants import ABSENT
from api.users.models import User
from api.users.roles import UserRoles
from api.leads_task.models import LeadTask
from api.leads_task.constants import LeadTaskStatus


EMMA_EMAIL = "emma.jacquin@papiers-express.fr"


def main():
    emma = User.objects.get(
        email=EMMA_EMAIL,
        role=UserRoles.ACCUEIL,
        is_active=True,
    )

    tasks_to_update = LeadTask.objects.filter(
        assigned_to__role=UserRoles.ACCUEIL,
        status=LeadTaskStatus.TODO,
    ).exclude(
        assigned_to=emma,
    )

    absent_tasks = tasks_to_update.filter(
        lead__status__code=ABSENT,
    )

    non_absent_tasks = tasks_to_update.exclude(
        lead__status__code=ABSENT,
    )

    duplicate_groups = (
        absent_tasks
        .values("lead_id", "task_type_id", "status")
        .annotate(total=Count("id"))
        .filter(total__gt=1)
        .order_by("-total")
    )

    duplicate_ids_to_delete = []

    for group in duplicate_groups:
        duplicates = list(
            absent_tasks.filter(
                lead_id=group["lead_id"],
                task_type_id=group["task_type_id"],
                status=group["status"],
            ).order_by("created_at", "id")
        )

        duplicate_ids_to_delete.extend([task.id for task in duplicates[1:]])

    print("\n=== RÉCAPITULATIF AVANT ACTION ===\n")
    print(f"Nouvelle assignée : {emma.get_full_name()} <{emma.email}>")
    print(f"Tâches ACCUEIL non traitées trouvées : {tasks_to_update.count()}")
    print(f"Tâches dont le lead est ABSENT : {absent_tasks.count()}")
    print(f"Tâches dont le lead n'est PAS ABSENT : {non_absent_tasks.count()}")
    print(f"Groupes de doublons ABSENT détectés : {duplicate_groups.count()}")
    print(f"Tâches doublons ABSENT à supprimer : {len(duplicate_ids_to_delete)}")
    print(f"Tâches ABSENT restantes à réassigner : {absent_tasks.count() - len(duplicate_ids_to_delete)}")

    if non_absent_tasks.exists():
        print("\n⚠️ Tâches ignorées car lead non ABSENT :")
        for task in non_absent_tasks.select_related("lead", "lead__status", "assigned_to")[:50]:
            print(
                f"- task_id={task.id} | "
                f"lead_id={task.lead_id} | "
                f"lead={task.lead.first_name} {task.lead.last_name} | "
                f"status_lead={task.lead.status.code if task.lead.status else 'AUCUN'} | "
                f"assigné={task.assigned_to.email if task.assigned_to else 'AUCUN'}"
            )

        if non_absent_tasks.count() > 50:
            print(f"... + {non_absent_tasks.count() - 50} autre(s) tâche(s) non ABSENT")

    print("\nDétail par utilisateur actuel pour les tâches ABSENT :")
    for row in (
        absent_tasks
        .values(
            "assigned_to__email",
            "assigned_to__first_name",
            "assigned_to__last_name",
        )
        .distinct()
        .order_by("assigned_to__email")
    ):
        count = absent_tasks.filter(
            assigned_to__email=row["assigned_to__email"]
        ).count()

        print(
            f"- {row['assigned_to__first_name']} "
            f"{row['assigned_to__last_name']} "
            f"<{row['assigned_to__email']}> : {count} tâche(s)"
        )

    if duplicate_ids_to_delete:
        print("\n⚠️ Doublons ABSENT qui seront supprimés :")
        for task_id in duplicate_ids_to_delete[:50]:
            print(f"- task_id={task_id}")

        if len(duplicate_ids_to_delete) > 50:
            print(f"... + {len(duplicate_ids_to_delete) - 50} autre(s) doublon(s)")

    confirm = input(
        "\nTape OUI pour supprimer les doublons ABSENT puis réassigner les tâches ABSENT à Emma : "
    )

    if confirm.strip() != "OUI":
        print("Opération annulée.")
        return

    with transaction.atomic():
        deleted_count = 0

        if duplicate_ids_to_delete:
            deleted_count, _ = LeadTask.objects.filter(
                id__in=duplicate_ids_to_delete
            ).delete()

        updated_count = LeadTask.objects.filter(
            assigned_to__role=UserRoles.ACCUEIL,
            status=LeadTaskStatus.TODO,
            lead__status__code=ABSENT,
        ).exclude(
            assigned_to=emma,
        ).update(
            assigned_to=emma,
        )

    print("\n✅ Terminé.")
    print(f"Doublons ABSENT supprimés : {deleted_count}")
    print(f"Tâches ABSENT réassignées à Emma : {updated_count}")


if __name__ == "__main__":
    main()