# api/appointments/test_models.py

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Appointment(models.Model):
    """
    Modèle représentant un rendez-vous lié à un lead,
    planifié par un utilisateur (conseiller, juriste, etc.).
    """

    id = models.AutoField(primary_key=True, verbose_name=_("ID"))

    lead = models.ForeignKey(
        "leads.Lead",
        on_delete=models.CASCADE,
        related_name="appointments",
        verbose_name=_("lead"),
        help_text=_("Lead concerné par ce rendez-vous"),
    )

    date = models.DateTimeField(
        verbose_name=_("date et heure du rendez-vous"),
        help_text=_("Date et heure du rendez-vous"),
    )

    note = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name=_("note"),
        help_text=_("Note ou objet du rendez-vous (optionnel)"),
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="appointments_created",
        verbose_name=_("créé par"),
        help_text=_("Utilisateur qui a planifié le rendez-vous"),
    )

    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name=_("date de création"),
        help_text=_("Date de création du rendez-vous"),
    )

    class Meta:
        verbose_name = _("rendez-vous")
        verbose_name_plural = _("rendez-vous")
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["date"], name="appointment_date_idx"),
            models.Index(fields=["lead"], name="appointment_lead_idx"),
            models.Index(fields=["created_by"], name="appointment_createdby_idx"),
        ]

    def __str__(self):
        return f"RDV {self.lead} le {self.date.strftime('%d/%m/%Y %H:%M')}"
