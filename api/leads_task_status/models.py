"""
api/leads/tasks/models_task_status.py
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class LeadTaskStatus(models.Model):
    """
    Statut d'une tâche liée à un lead.

    Exemple :
        - PENDING
        - IN_PROGRESS
        - DONE
        - CANCELLED
        - OVERDUE
    """

    code = models.CharField(
        max_length=40,
        unique=True,
        db_index=True,
        verbose_name=_("code"),
    )

    label = models.CharField(
        max_length=120,
        verbose_name=_("libellé"),
    )

    is_final = models.BooleanField(
        default=False,
        verbose_name=_("statut final"),
        help_text=_("Indique si la tâche est terminée ou bloquée."),
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("créé le"),
    )

    class Meta:
        verbose_name = _("statut tâche")
        verbose_name_plural = _("statuts tâches")
        ordering = ["label"]

    def __str__(self):
        return self.label