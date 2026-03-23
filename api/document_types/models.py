from django.db import models


class DocumentType(models.Model):
    """
    Type de document : passeport, carte d'identité, etc.
    """

    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Nom du type",
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Description",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création",
    )

    class Meta:
        verbose_name = "Type de document"
        verbose_name_plural = "Types de documents"
        ordering = ["name"]

    def __str__(self):
        return self.name