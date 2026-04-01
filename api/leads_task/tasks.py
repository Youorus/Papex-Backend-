# api/leads_task/tasks.py
# ✅ Migré Celery → Django-Q2 | Harmonisé, Résilient & Multi-assignation par Rôle

import logging
from django_q.tasks import async_task
from django.utils import timezone

from api.leads.models import Lead
from api.leads_task.models import LeadTask
from api.leads_task_type.models import LeadTaskType
from api.leads_task_status.models import LeadTaskStatus
from api.leads_events.models import LeadEvent
from api.users.models import User
from api.users.roles import UserRoles

logger = logging.getLogger(__name__)

# ================================================================
# 🧠 HELPERS DE RÉSILIENCE (CRÉATION AUTO SI ABSENT)
# ================================================================

TASK_TYPE_REGISTRY: dict[str, dict] = {
    "RELANCE_LEAD": {
        "label": "Relance lead",
        "description": "Rappeler le lead absent à son rendez-vous pour reprogrammer.",
    },
    "RAPPEL_RDV": {
        "label": "Rappel rendez-vous",
        "description": "Confirmer le rendez-vous avec le lead avant la date prévue.",
    },
}


def get_or_create_task_type(code: str) -> LeadTaskType:
    """Récupère ou crée dynamiquement le type de tâche."""
    defaults = TASK_TYPE_REGISTRY.get(code, {})
    task_type, created = LeadTaskType.objects.get_or_create(
        code=code,
        defaults={
            "label": defaults.get("label", code.replace("_", " ").title()),
            "description": defaults.get("description", ""),
            "is_active": True,
        },
    )
    if created:
        logger.info("🤖 LeadTaskType '%s' créé à la volée !", code)
    return task_type


def get_or_create_task_status(code: str = "A_FAIRE") -> LeadTaskStatus:
    """Récupère ou crée le statut (ex: A_FAIRE)."""
    status, created = LeadTaskStatus.objects.get_or_create(
        code=code,
        defaults={"label": "À faire"}
    )
    if created:
        logger.info("🤖 LeadTaskStatus '%s' créé à la volée !", code)
    return status


# ================================================================
# ⚙️ WORKER : RELANCE APRÈS ABSENCE (CIBLE LE RÔLE ACCUEIL)
# ================================================================

def _run_create_absent_followup_task(lead_id: int, triggered_event_id: int = None):
    lead = Lead.objects.filter(id=lead_id).select_related("status").first()
    if not lead:
        return

    # Anti-doublon Event global
    if LeadEvent.objects.filter(lead=lead, event_type__code="TASK_RELANCE_CREATED").exists():
        return

    task_type = get_or_create_task_type("RELANCE_LEAD")
    task_status = get_or_create_task_status("A_FAIRE")

    triggered_by_event = None
    if triggered_event_id:
        triggered_by_event = LeadEvent.objects.filter(id=triggered_event_id).first()

    # 🎯 FILTRAGE STRICT PAR RÔLE ACCUEIL ET COMPTE ACTIF
    accueil_users = list(User.objects.filter(role=UserRoles.ACCUEIL, is_active=True))

    if not accueil_users:
        logger.warning("[tasks] Aucun utilisateur avec le rôle ACCUEIL actif trouvé.")
        accueil_users = [None]

    due_at = timezone.now()
    created_tasks = []

    for user in accueil_users:
        # Anti-doublon par utilisateur
        if LeadTask.objects.filter(lead=lead, task_type=task_type, assigned_to=user,
                                   completed_at__isnull=True).exists():
            continue

        task = LeadTask.objects.create(
            lead=lead,
            task_type=task_type,
            status=task_status,
            title=f"Relance — absent au RDV",
            description="Le lead était absent. À rappeler pour reprogrammer.",
            due_at=due_at,
            assigned_to=user,
            triggered_by_event=triggered_by_event,
            metadata={"auto_created": True, "role_target": UserRoles.ACCUEIL},
        )
        created_tasks.append(task)

    if created_tasks:
        LeadEvent.log(
            lead=lead,
            event_code="TASK_RELANCE_CREATED",
            data={"task_ids": [t.id for t in created_tasks], "count": len(created_tasks)}
        )
        logger.info(f"✅ {len(created_tasks)} tâches créées pour le rôle ACCUEIL (Lead {lead_id})")


# ================================================================
# 🚀 API PUBLIQUE
# ================================================================

def create_absent_followup_task(lead_id: int, triggered_event_id: int = None):
    async_task("api.leads_task.tasks._run_create_absent_followup_task", lead_id, triggered_event_id, group="crm")

create_absent_followup_tasks = create_absent_followup_task


def create_auto_task(
        lead_id: int,
        task_type_code: str,
        title: str,
        description: str = "",
        assign_to_accueil: bool = False,
        assigned_user_id: int = None,
        due_in_minutes: int = 0,
        triggered_event_id: int = None,
        metadata: dict = None,
):
    """Dispatch la création d'une tâche automatique générique."""
    kwargs = {"group": "crm"}
    if due_in_minutes:
        from datetime import timedelta
        kwargs["scheduled"] = timezone.now() + timedelta(minutes=due_in_minutes)

    async_task(
        "api.leads_task.tasks._run_create_auto_task",
        lead_id,
        task_type_code,
        title,
        description,
        assign_to_accueil,
        assigned_user_id,
        triggered_event_id,
        metadata,
        **kwargs,
    )