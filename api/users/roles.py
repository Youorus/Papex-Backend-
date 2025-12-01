from django.db import models
from django.utils.translation import gettext_lazy as _


class UserRoles(models.TextChoices):
    """
    Rôles disponibles pour les utilisateurs.
    """

    ADMIN = "ADMIN", _("Administrateur")
    ACCUEIL = "ACCUEIL", _("Accueil")
    JURISTE = "JURISTE", _("Juriste")
    CONSEILLER = "CONSEILLER", _("Conseiller")
