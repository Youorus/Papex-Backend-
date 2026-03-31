"""
api/leads_task/tasks.py
✅ Migré de Celery vers Django-Q2

Automatisation des tâches liées aux leads.

Règles métier :
  - Une tâche de relance est créée pour CHAQUE utilisateur ACCUEIL actif
  - Le type de tâche est créé automatiquement s'il n'existe pas en base
  - Anti-doublon robuste par (lead, task_type, assigned_to)
  - Traçabilité complète via LeadEvent
"""

import logging

from django_q.tasks import async_task
from django.utils import timezone

from api.leads.models import Lead
from api.leads_task.models import LeadTask
from api.leads_task_type.models import LeadTaskType
from api.leads_task.constants import LeadTaskStatus
from api.leads_events.models import LeadEvent
from api.users.models import User
from api.users.roles import UserRoles

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# REGISTRE DES TYPES DE TÂCHES AUTOMATIQUES
# ─────────────────────────────────────────────────────────────

TASK_TYPE_REGISTRY: dict[str, dict] = {
    "RELANCE_LEAD": {
        "label": "Relance lead",
        "description": "Rappeler le lead absent à son rendez-vous pour reprogrammer.",
    },
    "RAPPEL_RDV": {
        "label": "Rappel rendez-vous",
        "description": "Confirmer le rendez-vous avec le lead avant la date prévue.",
    },
    "SUIVI_DOSSIER": {
        "label": "Suivi dossier",
        "description": "Faire le point sur l'avancement du dossier du lead.",
    },
    "ENVOI_DOCUMENT": {
        "label": "Envoi document",
        "description": "Envoyer ou relancer pour la transmission de documents.",
    },
}


def get_or_create_task_type(code: str, label: str = "", description: str = "") -> LeadTaskType:
    """
    Retourne le type de tâche correspondant au code donné.
    S'il n'existe pas, le crée automatiquement.
    """
    defaults = TASK_TYPE_REGISTRY.get(code, {})

    resolved_label = label or defaults.get("label") or code.replace("_", " ").capitalize()
    resolved_description = description or defaults.get("description", "")

    task_type, created = LeadTaskType.objects.get_or_create(
        code=code,
        defaults={
            "label": resolved_label,
            "description": resolved_description,
            "is_active": True,
        },
    )

    if created:
        logger.info(
            "[tasks] LeadTaskType '%s' créé automatiquement (label='%s')",
            code, resolved_label,
        )

    return task_type


# ─────────────────────────────────────────────────────────────
# FONCTION WORKER : RELANCE APRÈS ABSENCE
# ─────────────────────────────────────────────────────────────

def _run_create_absent_followup_tasks(lead_id: int, triggered_event_id: int = None):
    """
    Worker Django-Q2 — Crée une tâche de relance pour chaque utilisateur ACCUEIL actif
    lorsqu'un lead est marqué ABSENT.
    """
    lead = Lead.objects.filter(id=lead_id).select_related("status").first()

    if not lead:
        logger.warning(
            "[create_absent_followup_tasks] Lead #%s introuvable — ignoré",
            lead_id,
        )
        return

    task_type = get_or_create_task_type("RELANCE_LEAD")

    triggered_by_event = None
    if triggered_event_id:
        triggered_by_event = LeadEvent.objects.filter(id=triggered_event_id).first()

    accueil_users = list(
        User.objects.filter(role=UserRoles.ACCUEIL, is_active=True)
    )

    if not accueil_users:
        logger.warning(
            "[create_absent_followup_tasks] Aucun utilisateur ACCUEIL actif — "
            "tâche créée sans assignation : lead_id=%s",
            lead_id,
        )
        accueil_users = [None]

    rdv_str = (
        lead.appointment_date.strftime("%d/%m/%Y à %Hh%M")
        if lead.appointment_date
        else "RDV non daté"
    )

    title = f"Relance — absent au RDV du {rdv_str}"
    description = (
        "Le lead n'était pas présent à son rendez-vous.\n"
        "À rappeler dès que possible pour reprogrammer."
    )
    due_at = timezone.now()
    created_tasks = []

    for user in accueil_users:
        already_exists = LeadTask.objects.filter(
            lead=lead,
            task_type=task_type,
            assigned_to=user,
            completed_at__isnull=True,
        ).exists()

        if already_exists:
            logger.info(
                "[create_absent_followup_tasks] Tâche déjà existante — ignoré : "
                "lead_id=%s | user=%s",
                lead_id,
                user.id if user else "non assigné",
            )
            continue

        task = LeadTask.objects.create(
            lead=lead,
            task_type=task_type,
            status=LeadTaskStatus.TODO,
            title=title,
            description=description,
            due_at=due_at,
            assigned_to=user,
            triggered_by_event=triggered_by_event,
            metadata={
                "auto_created": True,
                "trigger": "ABSENT",
                "appointment_date": (
                    lead.appointment_date.isoformat()
                    if lead.appointment_date else None
                ),
                "assigned_to_id": user.id if user else None,
            },
        )

        created_tasks.append(task)

        logger.info(
            "[create_absent_followup_tasks] Tâche créée : task_id=%s | "
            "lead_id=%s | assigned_to=%s",
            task.id, lead.id,
            user.id if user else "non assigné",
        )

    if created_tasks:
        LeadEvent.log(
            lead=lead,
            event_code="TASK_RELANCE_CREATED",
            data={
                "task_ids": [t.id for t in created_tasks],
                "assigned_to_ids": [
                    t.assigned_to.id for t in created_tasks if t.assigned_to
                ],
                "count": len(created_tasks),
            },
        )
        logger.info(
            "[create_absent_followup_tasks] %s tâche(s) créée(s) pour lead_id=%s",
            len(created_tasks), lead_id,
        )
    else:
        logger.info(
            "[create_absent_followup_tasks] Aucune nouvelle tâche — "
            "toutes existaient déjà : lead_id=%s",
            lead_id,
        )


# ─────────────────────────────────────────────────────────────
# FONCTION WORKER : CRÉATION GÉNÉRIQUE À LA DEMANDE
# ─────────────────────────────────────────────────────────────

def _run_create_auto_task(
    lead_id: int,
    task_type_code: str,
    title: str,
    description: str = "",
    assign_to_accueil: bool = False,
    assigned_user_id: int = None,
    triggered_event_id: int = None,
    metadata: dict = None,
):
    """
    Worker Django-Q2 — Crée une tâche automatique avec auto-création du type.
    """
    lead = Lead.objects.filter(id=lead_id).select_related("status").first()

    if not lead:
        logger.warning("[create_auto_task] Lead #%s introuvable", lead_id)
        return

    task_type = get_or_create_task_type(task_type_code)

    triggered_by_event = None
    if triggered_event_id:
        triggered_by_event = LeadEvent.objects.filter(id=triggered_event_id).first()

    due_at = timezone.now()

    base_metadata = {"auto_created": True, "task_type_code": task_type_code}
    if metadata:
        base_metadata.update(metadata)

    if assign_to_accueil:
        users = list(User.objects.filter(role=UserRoles.ACCUEIL, is_active=True))
        if not users:
            users = [None]
    elif assigned_user_id:
        user = User.objects.filter(id=assigned_user_id).first()
        users = [user] if user else [None]
    else:
        users = [None]

    created_tasks = []

    for user in users:
        already_exists = LeadTask.objects.filter(
            lead=lead,
            task_type=task_type,
            assigned_to=user,
            completed_at__isnull=True,
        ).exists()

        if already_exists:
            continue

        task = LeadTask.objects.create(
            lead=lead,
            task_type=task_type,
            status=LeadTaskStatus.TODO,
            title=title,
            description=description,
            due_at=due_at,
            assigned_to=user,
            triggered_by_event=triggered_by_event,
            metadata={**base_metadata, "assigned_to_id": user.id if user else None},
        )

        created_tasks.append(task)

        logger.info(
            "[create_auto_task] Tâche '%s' créée : task_id=%s | lead_id=%s | user=%s",
            task_type_code, task.id, lead_id,
            user.id if user else "non assigné",
        )

    if created_tasks:
        LeadEvent.log(
            lead=lead,
            event_code="AUTO_TASK_CREATED",
            data={
                "task_type": task_type_code,
                "task_ids": [t.id for t in created_tasks],
                "count": len(created_tasks),
            },
        )


# ─────────────────────────────────────────────────────────────
# API PUBLIQUE — Fonctions de dispatch
# (remplacent les .delay() / .apply_async() de Celery)
# ─────────────────────────────────────────────────────────────

def create_absent_followup_tasks(lead_id: int, triggered_event_id: int = None):
    """
    Dispatch la création de tâches de relance après absence.
    Anciennement : create_absent_followup_tasks.delay(...)
    """
    async_task(
        "api.leads_task.tasks._run_create_absent_followup_tasks",
        lead_id,
        triggered_event_id,
        group="crm",
    )


# Alias pour compatibilité avec les anciens imports (status_changed.py)
create_absent_followup_task = create_absent_followup_tasks


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
    """
    Dispatch la création d'une tâche automatique générique.
    Anciennement : create_auto_task.delay(...)

    Note : due_in_minutes est géré directement dans le worker via timezone.now()
    au moment de l'exécution. Pour un délai important, passer scheduled= si besoin.
    """
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