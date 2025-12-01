from django.conf import settings
from django.db import models


class UserUnavailability(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="unavailabilities",
    )
    start_date = models.DateField()
    end_date = models.DateField()
    label = models.CharField(
        max_length=120, blank=True, help_text="Motif ou commentaire (optionnel)"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Indisponibilité utilisateur"
        verbose_name_plural = "Indisponibilités utilisateurs"
        ordering = ["-start_date", "-end_date"]

    def __str__(self):
        if self.start_date == self.end_date:
            return f"{self.user} absent le {self.start_date}"
        return f"{self.user} absent du {self.start_date} au {self.end_date}"
