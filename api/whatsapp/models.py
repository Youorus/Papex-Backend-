# api/whatsapp/models.py
from django.db import models
from api.leads.models import Lead


class WhatsAppMessage(models.Model):
    # Identifiant unique Meta (évite les doublons au webhook)
    wa_id = models.CharField(max_length=255, unique=True)

    # Lead associé (null si numéro inconnu)
    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        related_name="whatsapp_messages",
        null=True,
        blank=True,
    )

    # Numéro brut Meta (format international, ex: 33612345678)
    sender_phone = models.CharField(max_length=30)

    # Corps du message
    body = models.TextField()

    # True = envoyé depuis l'app, False = reçu du client
    is_outbound = models.BooleanField(default=False)

    # Lecture : True = lu par l'agent
    is_read = models.BooleanField(default=False)

    # Statut d'envoi côté Meta (sent / delivered / read / failed)
    delivery_status = models.CharField(
        max_length=20,
        default="sent",
        choices=[
            ("sent", "Envoyé"),
            ("delivered", "Délivré"),
            ("read", "Lu"),
            ("failed", "Échec"),
        ],
    )

    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "whatsapp"
        ordering = ["timestamp"]

    def __str__(self):
        direction = "→" if self.is_outbound else "←"
        lead_name = f"{self.lead.first_name} {self.lead.last_name}" if self.lead else self.sender_phone
        return f"{direction} {lead_name}: {self.body[:40]}"
