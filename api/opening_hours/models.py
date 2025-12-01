from datetime import datetime, timedelta

from django.db import models
from django.utils.translation import gettext_lazy as _


class OpeningHours(models.Model):
    """
    Horaires hebdomadaires récurrents (source de vérité).
    Ex : Lundi 09:00-18:00, créneaux 30min, capacité 2 rdv/slot.
    """

    DAY_CHOICES = [
        (0, _("Lundi")),
        (1, _("Mardi")),
        (2, _("Mercredi")),
        (3, _("Jeudi")),
        (4, _("Vendredi")),
        (5, _("Samedi")),
        (6, _("Dimanche")),
    ]

    day_of_week = models.IntegerField(
        choices=DAY_CHOICES,
        unique=True,
        help_text=_("Jour de la semaine (0 = Lundi, 6 = Dimanche)."),
    )
    open_time = models.TimeField(
        null=True, blank=True, help_text=_("Heure d'ouverture (HH:MM).")
    )
    close_time = models.TimeField(
        null=True, blank=True, help_text=_("Heure de fermeture (HH:MM).")
    )

    slot_duration_minutes = models.PositiveIntegerField(
        default=30, help_text=_("Durée d'un créneau en minutes (15, 20, 30…).")
    )
    capacity_per_slot = models.PositiveIntegerField(
        default=1, help_text=_("Nombre maximum de rendez-vous par créneau.")
    )
    is_active = models.BooleanField(
        default=True, help_text=_("Si désactivé, ce jour est considéré comme fermé.")
    )

    class Meta:
        ordering = ["day_of_week"]
        verbose_name = _("Horaire d'ouverture")
        verbose_name_plural = _("Horaires d'ouverture")

    @property
    def is_closed(self) -> bool:
        """Jour fermé si pas d'horaires ou désactivé."""
        return not (self.open_time and self.close_time and self.is_active)

    def __str__(self) -> str:
        if self.is_closed:
            return f"{self.get_day_of_week_display()}: Fermé"
        return (
            f"{self.get_day_of_week_display()}: "
            f"{self.open_time.strftime('%H:%M')} - {self.close_time.strftime('%H:%M')} "
            f"({self.slot_duration_minutes} min, cap {self.capacity_per_slot})"
        )
