# api/whatsapp/models.py
from django.db import models
from api.leads.models import Lead

class WhatsAppMessage(models.Model):
    # Identifiant unique du message chez Meta (pour éviter les doublons)
    wa_id = models.CharField(max_length=255, unique=True)
    # Lien automatique avec votre Lead (Nom/Prénom)
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="messages", null=True)
    # Le numéro brut (au cas où le lead n'existe pas encore)
    sender_phone = models.CharField(max_length=20)
    body = models.TextField()
    # Direction du message
    is_outbound = models.BooleanField(default=False) # True = envoyé par vous, False = reçu
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']