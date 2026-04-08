"""
api/leads_task/models.py

Gestion des tâches liées aux leads + commentaires.
"""

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from api.leads_events.models import LeadEvent
from api.leads_task_type.models import LeadTaskType
from api.leads_task.constants import LeadTaskStatus, LeadTaskPriority


class LeadTask(models.Model):
    """
    Tâche planifiée liée à un lead.
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

    status = models.CharField(
        max_length=30,
        choices=LeadTaskStatus.CHOICES,
        default=LeadTaskStatus.TODO,
        db_index=True,
        verbose_name=_("statut"),
    )

    priority = models.CharField(
        max_length=20,
        choices=LeadTaskPriority.CHOICES,
        default=LeadTaskPriority.MEDIUM,
        db_index=True,
        verbose_name=_("priorité"),
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
            models.Index(fields=["priority", "status"]),
        ]

    def __str__(self):
        return f"{self.task_type.label} — {self.lead}"

    # ──────────────────────────────────────────
    # MÉTHODES MÉTIER
    # ──────────────────────────────────────────

    def reschedule(self, new_due_at, reason="", rescheduled_by=None):
        """Replanifie la tâche et conserve l'historique."""
        history = {
            "old_due_at": self.due_at.isoformat(),
            "reason": reason,
            "rescheduled_by": str(rescheduled_by.id) if rescheduled_by else None,
            "at": timezone.now().isoformat(),
        }

        self.reschedule_history.append(history)
        self.reschedule_count += 1
        self.due_at = new_due_at

        if self.status == LeadTaskStatus.DONE:
            self.status = LeadTaskStatus.TODO
            self.completed_at = None

        self.save(
            update_fields=[
                "due_at",
                "reschedule_count",
                "reschedule_history",
                "status",
                "completed_at",
            ]
        )

        return self

    def complete(self):
        """Marque la tâche comme terminée."""
        self.completed_at = timezone.now()
        self.status = LeadTaskStatus.DONE
        self.save(update_fields=["completed_at", "status"])
        return self

    @property
    def is_overdue(self):
        """Indique si la tâche est en retard."""
        return self.completed_at is None and self.due_at < timezone.now()

    @property
    def comment_count(self):
        """Nombre de commentaires liés."""
        return self.comments.count()


class LeadTaskComment(models.Model):
    """
    Commentaire lié à une tâche de lead.
    """

    task = models.ForeignKey(
        LeadTask,
        on_delete=models.CASCADE,
        related_name="comments",
        verbose_name=_("tâche"),
    )

    author = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lead_task_comments",
        verbose_name=_("auteur"),
    )

    content = models.TextField(
        verbose_name=_("contenu"),
    )

    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name=_("créé le"),
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("modifié le"),
    )

    is_edited = models.BooleanField(
        default=False,
        verbose_name=_("modifié"),
    )

    class Meta:
        verbose_name = _("commentaire tâche")
        verbose_name_plural = _("commentaires tâche")
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["task", "created_at"]),
        ]

    def __str__(self):
        return f"Commentaire de {self.author} sur {self.task}"

    def save(self, *args, **kwargs):
        if self.pk:
            self.is_edited = True
        super().save(*args, **kwargs)