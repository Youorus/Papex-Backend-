from django.db import models
from django.utils.translation import gettext_lazy as _


class StatutDossierInterne(models.Model):
    """
    Modèle représentant un statut interne d’un dossier.
    Utilisé par les équipes internes pour suivre l’avancement du traitement.
    - code : identifiant unique (ex : "EN_ATTENTE", "EN_COURS", "VALIDE", "CLOS").
    - label : nom affiché dans l’interface interne.
    - description : explication courte de l’utilisation du statut.
    - color : couleur associée pour l’UI.
    """

    code = models.CharField(max_length=50, unique=True, verbose_name=_("code"))
    label = models.CharField(max_length=255, verbose_name=_("nom affiché"))
    description = models.TextField(blank=True, null=True, verbose_name=_("description"))
    color = models.CharField(
        max_length=10, default="#6b7280", verbose_name=_("couleur (hexa)")
    )

    class Meta:
        verbose_name = _("statut interne de dossier")
        verbose_name_plural = _("statuts internes de dossier")
        ordering = ["label"]

    def __str__(self):
        return f"{self.label} ({self.code})"