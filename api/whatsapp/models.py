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
    body = models.TextField(blank=True, default="")
    is_outbound = models.BooleanField(default=False)
    is_read = models.BooleanField(default=False)

    # ── Pièces jointes ────────────────────────────────────────────────────────
    # Le media_id est l'identifiant Meta pour télécharger le média via l'API.
    # media_url est l'URL signée (durée de vie limitée ~5 min) récupérée après coup.
    # media_mime_type stocke le vrai MIME type renvoyé par Meta (image/jpeg, audio/ogg, etc.)
    media_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="ID Meta du média (utilisé pour télécharger via l'API Graph)",
    )
    media_url = models.TextField(
        blank=True,
        null=True,
        help_text="URL signée du média (valide ~5 min après récupération)",
    )
    media_mime_type = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="MIME type du média (image/jpeg, audio/ogg;codecs=opus, video/mp4, etc.)",
    )
    media_caption = models.TextField(
        blank=True,
        null=True,
        help_text="Légende optionnelle accompagnant le média",
    )
    media_filename = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Nom de fichier original (pour les documents)",
    )

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

    # Timestamp réel du message selon Meta (peut différer de created_at)
    # null=True permet la migration sur les lignes existantes ; le save() renseigne toujours la valeur.
    timestamp = models.DateTimeField(
        db_index=True,
        null=True,
        blank=True,
        help_text="Timestamp réel du message (fourni par Meta ou auto au moment de la création)",
    )
    # created_at : null=True uniquement pour la migration, toujours renseigné en pratique
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        app_label = "whatsapp"
        ordering = ["timestamp"]

    def save(self, *args, **kwargs):
        # Si timestamp non défini (ex: message sortant créé manuellement), on met l'heure actuelle
        if not self.timestamp:
            from django.utils import timezone
            self.timestamp = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        direction = "→" if self.is_outbound else "←"
        lead_name = f"{self.lead.first_name} {self.lead.last_name}" if self.lead else self.sender_phone
        return f"{direction} {lead_name}: {self.body[:40]}"

    @property
    def message_type(self) -> str:
        """Retourne le type de message : 'text', 'image', 'audio', 'video', 'document', 'sticker'"""
        if not self.media_id:
            return "text"
        if self.media_mime_type:
            if self.media_mime_type.startswith("image/"):
                return "image"
            if self.media_mime_type.startswith("audio/"):
                return "audio"
            if self.media_mime_type.startswith("video/"):
                return "video"
            if self.media_mime_type == "application/pdf" or "document" in self.media_mime_type:
                return "document"
        return "document"


class WhatsAppConversationSettings(models.Model):
    """
    Paramètres par conversation WhatsApp.
    Une entrée par identifiant unique de conversation :
      - soit via lead_id (FK)
      - soit via sender_phone pour les inconnus

    agent_enabled = True  → Sarah répond automatiquement (défaut)
    agent_enabled = False → mode manuel, un humain prend la main
    """

    lead = models.OneToOneField(
        Lead,
        on_delete=models.CASCADE,
        related_name="whatsapp_settings",
        null=True,
        blank=True,
    )

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
        obj, _ = cls.objects.get_or_create(lead=lead, defaults={"agent_enabled": True})
        return obj

    @classmethod
    def get_for_phone(cls, phone: str) -> "WhatsAppConversationSettings":
        obj, _ = cls.objects.get_or_create(
            lead__isnull=True,
            sender_phone=phone,
            defaults={"agent_enabled": True},
        )
        return obj

    @classmethod
    def is_agent_enabled(cls, lead=None, phone: str = None) -> bool:
        try:
            if lead:
                return cls.objects.get(lead=lead).agent_enabled
            elif phone:
                return cls.objects.get(lead__isnull=True, sender_phone=phone).agent_enabled
        except cls.DoesNotExist:
            pass
        return True