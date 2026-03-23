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

    # ✅ AJOUT ICI
    document_type = models.ForeignKey(
        "document_types.DocumentType",  # ⚠️ important : app_label.ModelName
        on_delete=models.PROTECT,
        related_name="documents",
        verbose_name="Type de document",
        blank=True,
        null=True,
    )

    url = models.URLField(verbose_name="URL du document")

    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date d’envoi",
    )

    class Meta:
        verbose_name = "Document"
        verbose_name_plural = "Documents"
        ordering = ["-uploaded_at"]

    def __str__(self):
        file_name = self.url.split("/")[-1]
        document_type = self.document_type.name if self.document_type else "Sans type"
        return f"{self.client} — {document_type} — {file_name}"