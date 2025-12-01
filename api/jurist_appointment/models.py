# test_models.py

from django.conf import settings
from django.db import models
from django.utils import timezone


class JuristAppointment(models.Model):
    lead = models.ForeignKey(
        "leads.Lead", on_delete=models.CASCADE, related_name="jurist_appointments"
    )
    jurist = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={"role": "JURISTE"},
        related_name="jurist_appointments",
    )
    date = models.DateTimeField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="jurist_appointments_created",
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("jurist", "date")
        ordering = ["-date"]

    def __str__(self):
        return (
            f"{self.lead} avec {self.jurist} le {self.date.strftime('%d/%m/%Y %H:%M')}"
        )
