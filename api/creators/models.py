import uuid
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from api.storage_backends import MinioCreatorContractStorage


def creator_contract_path(instance, filename):
    return f"creator_{instance.creator.id}/{filename}"


class CreatorProfile(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", _("En attente")
        ACTIVE = "ACTIVE", _("Actif")
        PAUSED = "PAUSED", _("En pause")
        DISABLED = "DISABLED", _("Désactivé")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="creator_profile",
    )
    phone_number = models.CharField(
        max_length=20, blank=True, null=True, verbose_name=_("Numéro de téléphone")
    )
    country = models.CharField(
        max_length=100, blank=True, null=True, verbose_name=_("Pays")
    )
    city = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Ville"))
    currency = models.CharField(
        max_length=3,
        default="EUR",
        verbose_name=_("Devise (Code ISO)"),
        help_text=_("Ex: EUR, USD, XOF, etc.")
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        verbose_name=_("Statut"),
    )
    notes = models.TextField(blank=True, null=True, verbose_name=_("Notes"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Créé le"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Mis à jour le"))

    class Meta:
        verbose_name = _("Profil Créateur")
        verbose_name_plural = _("Profils Créateurs")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return self.user.get_full_name() or self.user.email

    def save(self, *args, **kwargs):
        # If status is DISABLED, we also deactivate the associated user
        if self.status == self.Status.DISABLED:
            if self.user.is_active:
                self.user.is_active = False
                self.user.save(update_fields=['is_active'])
        
        super().save(*args, **kwargs)


class PromoCode(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", _("Actif")
        INACTIVE = "INACTIVE", _("Inactif")
        EXPIRED = "EXPIRED", _("Expiré")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        verbose_name=_("Code"),
    )
    creator = models.ForeignKey(
        CreatorProfile,
        on_delete=models.CASCADE,
        related_name="promo_codes",
        verbose_name=_("Créateur"),
    )
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=10.00,
        verbose_name=_("Taux de commission"),
    )
    bonus_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        verbose_name=_("Montant du bonus"),
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
        verbose_name=_("Statut"),
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Description"),
    )
    valid_until = models.DateField(
        blank=True,
        null=True,
        verbose_name=_("Valide jusqu'au"),
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Créé le"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Mis à jour le"))

    class Meta:
        verbose_name = _("Code Promo")
        verbose_name_plural = _("Codes Promo")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["code"]),
            models.Index(fields=["creator"]),
        ]

    def __str__(self):
        return f"{self.code} ({self.creator.user.get_full_name()})"


class CreatorContract(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255, verbose_name=_("Titre du contrat"))
    file = models.FileField(
        upload_to=creator_contract_path,
        storage=MinioCreatorContractStorage(),
        verbose_name=_("Fichier"),
    )
    creator = models.ForeignKey(
        CreatorProfile,
        on_delete=models.CASCADE,
        related_name="contracts",
        verbose_name=_("Créateur"),
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Créé le"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Mis à jour le"))

    class Meta:
        verbose_name = _("Contrat Créateur")
        verbose_name_plural = _("Contrats Créateurs")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} - {self.creator.user.get_full_name()}"

class SocialAccountLead(models.Model):
    class Platform(models.TextChoices):
        TIKTOK = "TIKTOK", _("TikTok")
        INSTAGRAM = "INSTAGRAM", _("Instagram")
        FACEBOOK = "FACEBOOK", _("Facebook")
        YOUTUBE = "YOUTUBE", _("YouTube")
        LINKEDIN = "LINKEDIN", _("LinkedIn")
        OTHER = "OTHER", _("Autre")

    class ContactStatus(models.TextChoices):
        NEW = "NEW", _("Nouveau")
        TO_CONTACT = "TO_CONTACT", _("À contacter")
        CONTACTED = "CONTACTED", _("Contacté")
        POSITIVE = "POSITIVE", _("Positif")
        NEGATIVE = "NEGATIVE", _("Négatif")
        CONVERTED = "CONVERTED", _("Converti")
        NOT_RELEVANT = "NOT_RELEVANT", _("Non pertinent")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    platform = models.CharField(
        max_length=20,
        choices=Platform.choices,
        db_index=True,
        verbose_name=_("Plateforme"),
    )

    username = models.CharField(
        max_length=150,
        verbose_name=_("Nom d'utilisateur"),
    )

    display_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_("Nom affiché"),
    )

    profile_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name=_("URL du profil"),
    )

    followers_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Nombre d'abonnés"),
    )

    bio = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Biographie"),
    )

    country = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
        verbose_name=_("Pays"),
    )

    language = models.CharField(
        max_length=30,
        blank=True,
        null=True,
        db_index=True,
        verbose_name=_("Langue"),
    )

    categories = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        db_index=True,
        verbose_name=_("Catégories"),
        help_text=_("Exemple : business, emploi, lifestyle, étudiant"),
    )

    source = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        db_index=True,
        verbose_name=_("Source"),
        help_text=_("Exemple : scrape_tiktok_ci_20260518, import_csv, manuel"),
    )

    is_viable = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name=_("Viable"),
    )

    contact_status = models.CharField(
        max_length=20,
        choices=ContactStatus.choices,
        default=ContactStatus.NEW,
        db_index=True,
        verbose_name=_("Statut du contact"),
    )

    creator = models.ForeignKey(
        CreatorProfile,
        on_delete=models.SET_NULL,
        related_name="social_leads",
        blank=True,
        null=True,
        verbose_name=_("Créateur"),
    )

    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Notes"),
    )

    raw_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Données brutes"),
        help_text=_("Ligne CSV originale ou payload brut de scraping."),
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Créé le"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Mis à jour le"))

    class Meta:
        verbose_name = _("Compte Social Prospect")
        verbose_name_plural = _("Comptes Sociaux Prospects")
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["platform", "username"],
                name="unique_platform_username",
            )
        ]
        indexes = [
            models.Index(fields=["platform"]),
            models.Index(fields=["contact_status"]),
            models.Index(fields=["is_viable"]),
            models.Index(fields=["country"]),
            models.Index(fields=["language"]),
            models.Index(fields=["source"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.username} on {self.get_platform_display()}"
