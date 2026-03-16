"""
api/leads/tasks/models.py

Gestion des tâches liées aux leads.

Les tâches permettent :
    - le suivi commercial
    - les rappels
    - les automatisations CRM
    - les workflows

Compatible avec :
    ✔ Celery
    ✔ automatisations
    ✔ audit trail
"""

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from api.leads_events.models import LeadEvent
from api.leads_task_status.models import LeadTaskStatus
from api.leads_task_type.models import LeadTaskType


class LeadTask(models.Model):
    """
    Tâche planifiée liée à un lead.

    Utilisée pour :
        - relances commerciales
        - rappels de RDV
        - suivi de dossier
        - automatisations CRM

    Une tâche peut être :
        ✔ créée manuellement
        ✔ déclenchée automatiquement par un événement
    """

    lead = models.ForeignKey(
        "leads.Lead",
        on_delete=models.CASCADE,
        related_name="tasks",
        verbose_name=_("lead"),
    )

    task_type = models.ForeignKey(
        LeadTaskType,
        on_delete=models.PROTECT,
        related_name="tasks",
        verbose_name=_("type de tâche"),
    )

    status = models.ForeignKey(
        LeadTaskStatus,
        on_delete=models.PROTECT,
        related_name="tasks",
        verbose_name=_("statut"),
    )

    title = models.CharField(
        max_length=200,
        verbose_name=_("titre"),
    )

    description = models.TextField(
        blank=True,
        verbose_name=_("description"),
    )

    due_at = models.DateTimeField(
        db_index=True,
        verbose_name=_("échéance"),
    )

    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name=_("créée le"),
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("complétée le"),
    )

    assigned_to = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lead_tasks",
        verbose_name=_("assignée à"),
    )

    created_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_lead_tasks",
        verbose_name=_("créée par"),
    )

    reschedule_count = models.PositiveSmallIntegerField(
        default=0,
        verbose_name=_("nombre de replanifications"),
    )

    reschedule_history = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("historique des replanifications"),
    )

    triggered_by_event = models.ForeignKey(
        LeadEvent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="triggered_tasks",
        verbose_name=_("déclenchée par l'événement"),
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("métadonnées"),
    )

    class Meta:
        verbose_name = _("tâche lead")
        verbose_name_plural = _("tâches lead")
        ordering = ["due_at"]
        indexes = [
            models.Index(fields=["lead", "due_at"]),
            models.Index(fields=["status", "due_at"]),
            models.Index(fields=["assigned_to", "status"]),
        ]

    def __str__(self):
        return f"{self.task_type.label} — {self.lead}"

    # ──────────────────────────────────────────
    # MÉTHODES MÉTIER
    # ──────────────────────────────────────────

    def reschedule(self, new_due_at, reason="", rescheduled_by=None):
        """
        Replanifie la tâche et conserve l'historique.
        """

        history = {
            "old_due_at": self.due_at.isoformat(),
            "reason": reason,
            "rescheduled_by": rescheduled_by.id if rescheduled_by else None,
            "at": timezone.now().isoformat(),
        }

        self.reschedule_history.append(history)
        self.reschedule_count += 1
        self.due_at = new_due_at

        self.save(
            update_fields=[
                "due_at",
                "reschedule_count",
                "reschedule_history",
            ]
        )

        return self

    def complete(self):
        """
        Marque la tâche comme terminée.
        """

        self.completed_at = timezone.now()
        self.save(update_fields=["completed_at"])

        return self

    @property
    def is_overdue(self):
        """
        Indique si la tâche est en retard.
        """

        return (
            self.completed_at is None
            and self.due_at < timezone.now()
        )