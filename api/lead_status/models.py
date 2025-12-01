from django.db import models
from django.utils.translation import gettext_lazy as _


class LeadStatus(models.Model):
    """
    Modèle représentant un statut possible pour un Lead.
    Permet de définir dynamiquement les différents états du cycle de vie d’un lead
    (ex : RDV_PLANIFIE, RDV_CONFIRME, ABSENT...), leur libellé et leur couleur pour l’UI.
    """

    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name=_("code"),
        help_text=_(
            "Code unique du statut, utilisé pour l'intégration et la logique métier (ex: RDV_CONFIRME)."
        ),
    )
    label = models.CharField(
        max_length=1000,
        verbose_name=_("libellé"),
        help_text=_("Libellé affiché dans l'interface (ex: 'Rendez-vous confirmé')."),
    )
    color = models.CharField(
        max_length=10,
        default="#333333",
        verbose_name=_("couleur"),
        help_text=_("Couleur associée au statut pour affichage (ex: #33C29C)."),
    )

    class Meta:
        verbose_name = _("statut de lead")
        verbose_name_plural = _("statuts de lead")
        ordering = ["label"]

    def __str__(self):
        """
        Affichage textuel : retourne le libellé du statut.
        """
        return f"{self.label}"
