from django.db import models
from api.leads.models import Lead


class WhatsAppMessage(models.Model):
    wa_id = models.CharField(max_length=255, unique=True)

    lead = models.ForeignKey(
        Lead,
        on_delete=models.SET_NULL,
        related_name="whatsapp_messages",
        null=True,
        blank=True,
    )

    sender_phone = models.CharField(max_length=30, db_index=True)
    body = models.TextField()
    is_outbound = models.BooleanField(default=False)
    is_read = models.BooleanField(default=False)

    delivery_status = models.CharField(
        max_length=20,
        default="sent",
        choices=[
            ("sent", "Envoyé"),
            ("delivered", "Délivré"),
            ("read", "Lu"),
            ("failed", "Échec"),
            ("received", "Reçu"),
        ],
    )

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = "whatsapp"
        ordering = ["timestamp"]

    def __str__(self):
        direction = "→" if self.is_outbound else "←"
        lead_name = f"{self.lead.first_name} {self.lead.last_name}" if self.lead else self.sender_phone
        return f"{direction} {lead_name}: {self.body[:40]}"