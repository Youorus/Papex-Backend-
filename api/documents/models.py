from django.db import models


class Document(models.Model):
    """
    Document lié à un client, stocké dans un cloud bucket (S3/MinIO…).
    """

    client = models.ForeignKey(
        "clients.Client",
        on_delete=models.CASCADE,
        related_name="documents",
        verbose_name="Client associé",
    )
    url = models.URLField(verbose_name="URL du document")
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="Date d’envoi")

    class Meta:
        verbose_name = "Document"
        verbose_name_plural = "Documents"
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.client} — {self.url.split('/')[-1]}"
