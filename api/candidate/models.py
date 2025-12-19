from django.db import models
from django.utils.translation import gettext_lazy as _

from api.job.models import Job


class Candidate(models.Model):
    """
    Modèle représentant une candidature à une offre d'emploi.
    Le CV est stocké sous forme d'URL (pas de fichier uploadé par Django).
    """

    class Status(models.TextChoices):
        PENDING = "pending", _("En attente")
        APPROVED = "approved", _("Validée")
        REJECTED = "rejected", _("Refusée")

    # Offre liée
    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name="candidates",
        verbose_name=_("offre d'emploi"),
    )

    # Infos candidat
    first_name = models.CharField(_("prénom"), max_length=100)
    last_name = models.CharField(_("nom"), max_length=100)
    email = models.EmailField(_("email"))

    # ✅ CV = URL
    cv_url = models.URLField(
        _("URL du CV"),
        max_length=500,
        help_text=_("Lien vers le CV (PDF, Drive, S3, etc.)"),
    )

    # Statut
    status = models.CharField(
        _("statut"),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    # Dates
    created_at = models.DateTimeField(_("candidature envoyée le"), auto_now_add=True)
    updated_at = models.DateTimeField(_("modifiée le"), auto_now=True)

    class Meta:
        verbose_name = _("candidature")
        verbose_name_plural = _("candidatures")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["job"]),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} – {self.job.title}"
