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


class WhatsAppConversationSettings(models.Model):
    """
    Paramètres par conversation WhatsApp.
    Une entrée par identifiant unique de conversation :
      - soit via lead_id (FK)
      - soit via sender_phone pour les inconnus

    agent_enabled = True  → Sarah répond automatiquement (défaut)
    agent_enabled = False → mode manuel, un humain prend la main
    """

    # Conversation liée à un lead connu
    lead = models.OneToOneField(
        Lead,
        on_delete=models.CASCADE,
        related_name="whatsapp_settings",
        null=True,
        blank=True,
    )

    # Conversation inconnue (pas encore de lead)
    sender_phone = models.CharField(
        max_length=30,
        db_index=True,
        null=True,
        blank=True,
    )

    agent_enabled = models.BooleanField(
        default=True,
        verbose_name="Agent IA actif",
        help_text="Si False, l'agent ne répond plus automatiquement pour cette conversation.",
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "whatsapp"
        verbose_name = "Paramètres conversation WhatsApp"
        verbose_name_plural = "Paramètres conversations WhatsApp"
        # Contrainte : soit lead soit phone, jamais les deux
        constraints = [
            models.UniqueConstraint(
                fields=["sender_phone"],
                condition=models.Q(lead__isnull=True),
                name="unique_unknown_phone_settings",
            )
        ]

    def __str__(self):
        target = f"Lead #{self.lead_id}" if self.lead_id else self.sender_phone
        status = "✅ actif" if self.agent_enabled else "⏸ pausé"
        return f"Agent {status} — {target}"

    @classmethod
    def get_for_lead(cls, lead) -> "WhatsAppConversationSettings":
        """Récupère ou crée les settings pour un lead connu."""
        obj, _ = cls.objects.get_or_create(lead=lead, defaults={"agent_enabled": True})
        return obj

    @classmethod
    def get_for_phone(cls, phone: str) -> "WhatsAppConversationSettings":
        """Récupère ou crée les settings pour un inconnu."""
        obj, _ = cls.objects.get_or_create(
            lead__isnull=True,
            sender_phone=phone,
            defaults={"agent_enabled": True},
        )
        return obj

    @classmethod
    def is_agent_enabled(cls, lead=None, phone: str = None) -> bool:
        """Raccourci : retourne True si l'agent est actif pour cette conversation."""
        try:
            if lead:
                return cls.objects.get(lead=lead).agent_enabled
            elif phone:
                return cls.objects.get(lead__isnull=True, sender_phone=phone).agent_enabled
        except cls.DoesNotExist:
            pass
        # Par défaut : actif
        return True