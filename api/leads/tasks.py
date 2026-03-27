"""
api/leads_task/tasks.py

Automatisation des tâches liées aux leads.

Règles métier :
  - Une tâche de relance est créée pour CHAQUE utilisateur ACCUEIL actif
  - Le type de tâche est créé automatiquement s'il n'existe pas en base
  - Anti-doublon robuste par (lead, task_type, assigned_to) pour éviter les doublons par utilisateur
  - Traçabilité complète via LeadEvent
"""

import logging

from celery import shared_task
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
#
# Chaque entrée définit un type de tâche connu du système.
# Si le code n'existe pas en base, il sera créé automatiquement
# lors du premier déclenchement.
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
    S'il n'existe pas, le crée automatiquement à partir du registre
    ou des paramètres fournis en fallback.

    Usage :
        task_type = get_or_create_task_type("RELANCE_LEAD")
        task_type = get_or_create_task_type("MON_CODE", label="Mon label", description="...")
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
# TASK PRINCIPALE : RELANCE APRÈS ABSENCE
# ─────────────────────────────────────────────────────────────

@shared_task
def create_absent_followup_tasks(lead_id: int, triggered_event_id: int = None):
    """
    Crée une tâche de relance POUR CHAQUE utilisateur ACCUEIL actif
    lorsqu'un lead est marqué ABSENT.

    Comportement :
      ✔ Type de tâche créé automatiquement si absent en base
      ✔ Anti-doublon par (lead, task_type, assigned_to)
      ✔ Événement de traçabilité global (une seule fois par lead)
      ✔ Un log par tâche créée
    """

    # ── Récupération du lead ──────────────────────────────────
    lead = Lead.objects.filter(id=lead_id).select_related("status").first()

    if not lead:
        logger.warning(
            "[create_absent_followup_tasks] Lead #%s introuvable — ignoré",
            lead_id,
        )
        return

    # ── Type de tâche (auto-créé si manquant) ─────────────────
    task_type = get_or_create_task_type("RELANCE_LEAD")

    # ── Événement déclencheur ─────────────────────────────────
    triggered_by_event = None
    if triggered_event_id:
        triggered_by_event = LeadEvent.objects.filter(id=triggered_event_id).first()

    # ── Utilisateurs ACCUEIL actifs ───────────────────────────
    accueil_users = list(
        User.objects.filter(role=UserRoles.ACCUEIL, is_active=True)
    )

    if not accueil_users:
        logger.warning(
            "[create_absent_followup_tasks] Aucun utilisateur ACCUEIL actif — "
            "tâche créée sans assignation : lead_id=%s",
            lead_id,
        )
        accueil_users = [None]  # Crée quand même une tâche non assignée

    # ── Libellé et description ────────────────────────────────
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

    # ── Création d'une tâche par utilisateur ACCUEIL ──────────
    created_tasks = []

    for user in accueil_users:

        # Anti-doublon par (lead, task_type, assigned_to)
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
            task.id,
            lead.id,
            user.id if user else "non assigné",
        )

    # ── Traçabilité globale (une seule fois par lead) ─────────
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
            len(created_tasks),
            lead_id,
        )
    else:
        logger.info(
            "[create_absent_followup_tasks] Aucune nouvelle tâche — "
            "toutes existaient déjà : lead_id=%s",
            lead_id,
        )


# ─────────────────────────────────────────────────────────────
# TASK GÉNÉRIQUE : CRÉATION À LA DEMANDE
#
# Utilisable depuis n'importe quel workflow pour créer
# une tâche automatique avec auto-création du type.
# ─────────────────────────────────────────────────────────────

@shared_task
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
    Crée une tâche automatique pour un lead avec auto-création du type.

    Paramètres :
        lead_id             : ID du lead cible
        task_type_code      : Code du type de tâche (créé si absent)
        title               : Titre de la tâche
        description         : Description optionnelle
        assign_to_accueil   : Si True, crée une tâche par utilisateur ACCUEIL actif
        assigned_user_id    : Assigner à un utilisateur précis (ignoré si assign_to_accueil=True)
        due_in_minutes      : Délai avant échéance (0 = maintenant)
        triggered_event_id  : ID de l'événement déclencheur
        metadata            : Données libres additionnelles
    """
    lead = Lead.objects.filter(id=lead_id).select_related("status").first()

    if not lead:
        logger.warning("[create_auto_task] Lead #%s introuvable", lead_id)
        return

    task_type = get_or_create_task_type(task_type_code)

    triggered_by_event = None
    if triggered_event_id:
        triggered_by_event = LeadEvent.objects.filter(id=triggered_event_id).first()

    due_at = timezone.now() + timezone.timedelta(minutes=due_in_minutes)

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