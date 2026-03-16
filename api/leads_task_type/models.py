"""
Modèle représentant les types de tâches CRM.

Permet de configurer dynamiquement les types de tâches
utilisées dans le suivi des leads.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class LeadTaskType(models.Model):
    """
    Type de tâche disponible pour un lead.

    Exemples :
        - Rappel RDV
        - Relance lead
        - Suivi dossier
        - Envoi document
        - Appel sortant
        - Personnalisée
    """

    code = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        verbose_name=_("code"),
        help_text=_("Identifiant technique du type de tâche (ex: RAPPEL_RDV)"),
    )

    label = models.CharField(
        max_length=120,
        verbose_name=_("libellé"),
    )

    description = models.TextField(
        blank=True,
        verbose_name=_("description"),
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name=_("actif"),
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("créé le"),
    )

    class Meta:
        verbose_name = _("type de tâche lead")
        verbose_name_plural = _("types de tâches lead")
        ordering = ["label"]

    def __str__(self):
        return self.label