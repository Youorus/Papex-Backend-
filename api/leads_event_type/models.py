"""
api/leads/events/models.py

Définition des types d'événements utilisés dans l'historique des leads.

Ces types sont configurables afin de permettre :
    - l'ajout dynamique de nouveaux événements
    - la personnalisation métier
    - la gestion via l'admin ou API
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class LeadEventType(models.Model):
    """
    Représente un type d'événement pouvant apparaître dans l'historique
    d'un lead.

    Exemple de types :
        STATUS_CHANGED
        APPOINTMENT_SET
        EMAIL_SENT
        TASK_CREATED
    """

    code = models.CharField(
        max_length=60,
        unique=True,
        db_index=True,
        verbose_name=_("code"),
        help_text=_("Code technique unique utilisé par le backend."),
    )

    label = models.CharField(
        max_length=120,
        verbose_name=_("libellé"),
        help_text=_("Nom affiché dans l'interface."),
    )

    description = models.TextField(
        blank=True,
        verbose_name=_("description"),
        help_text=_("Description métier du type d'événement."),
    )

    is_system = models.BooleanField(
        default=False,
        verbose_name=_("événement système"),
        help_text=_(
            "Empêche la suppression si utilisé par la logique métier."
        ),
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("créé le"),
    )

    class Meta:
        verbose_name = _("type d'événement lead")
        verbose_name_plural = _("types d'événements lead")
        ordering = ["label"]

    def __str__(self):
        return f"{self.label} ({self.code})"