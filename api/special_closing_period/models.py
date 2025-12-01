# models/special_closing_period.py

from django.db import models
from django.utils.translation import gettext_lazy as _


class SpecialClosingPeriod(models.Model):
    """
    Période de fermeture exceptionnelle (jours fériés, vacances, fermetures ponctuelles).
    Peut être définie avec des heures précises (bornes inclusives).
    Exemple :
    - 7 octobre de 15h à 20h
    - du 1 janvier 10h au 2 janvier 14h
    """

    label = models.CharField(
        max_length=100,
        help_text=_("Nom ou motif de la fermeture (ex : 'Noël', 'Vacances d'été', 'Travaux', etc.)"),
    )
    start_datetime = models.DateTimeField(
        help_text=_("Début de la fermeture (date + heure)")
    )
    end_datetime = models.DateTimeField(
        help_text=_("Fin de la fermeture (date + heure)")
    )

    class Meta:
        ordering = ["start_datetime"]
        verbose_name = _("Fermeture exceptionnelle")
        verbose_name_plural = _("Fermetures exceptionnelles")

    def __str__(self):
        start_str = self.start_datetime.strftime("%d/%m/%Y %H:%M")
        end_str = self.end_datetime.strftime("%d/%m/%Y %H:%M")
        if self.start_datetime.date() == self.end_datetime.date():
            return f"{self.label} : {self.start_datetime.strftime('%d/%m/%Y')} de {self.start_datetime.strftime('%H:%M')} à {self.end_datetime.strftime('%H:%M')}"
        return f"{self.label} : du {start_str} au {end_str}"