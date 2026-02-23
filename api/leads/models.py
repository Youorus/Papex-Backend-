from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError

from api.leads.constants import (
    RDV_PRESENTIEL,
    APPOINTMENT_TYPE_CHOICES,
    RDV_CONFIRME,
    RDV_PLANIFIE,
    LeadSource,
    BlockingDurationBucket,
)

from api.lead_status.models import LeadStatus
from api.services.models import Service


class Lead(models.Model):
    """
    Modèle représentant un prospect (Lead) utilisé pour le suivi commercial.
    """

    id = models.AutoField(primary_key=True, verbose_name=_("ID"))

    # 👤 Infos prospect
    first_name = models.CharField(max_length=150, verbose_name=_("prénom"))
    last_name = models.CharField(max_length=150, verbose_name=_("nom"))
    email = models.EmailField(blank=True, null=True, verbose_name=_("email"))
    phone = models.CharField(max_length=20, verbose_name=_("téléphone"))

    # 🧾 Suivi dossier
    statut_dossier = models.ForeignKey(
        "statut_dossier.StatutDossier",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name=_("statut du dossier"),
    )
    statut_dossier_interne = models.ForeignKey(
        "statut_dossier_interne.StatutDossierInterne",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name=_("statut du dossier interne"),
    )

    # 📅 RDV
    appointment_date = models.DateTimeField(blank=True, null=True, verbose_name=_("date de rendez-vous"))
    last_reminder_sent = models.DateTimeField(null=True, blank=True, verbose_name=_("dernier rappel envoyé"))

    appointment_type = models.CharField(
        max_length=20,
        choices=APPOINTMENT_TYPE_CHOICES,
        default=RDV_PRESENTIEL,
        verbose_name=_("type de rendez-vous"),
    )

    # 🧭 Qualification lead
    service = models.ForeignKey(
        Service,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="leads",
        verbose_name=_("service demandé"),
    )

    department_code = models.CharField(
        max_length=10,
        blank=True,
        verbose_name=_("département"),
        help_text=_("Département du prospect en France (ex: 75, 2A, 971)"),
    )

    is_urgent = models.BooleanField(default=False, verbose_name=_("situation urgente"))

    # ⭐ Durée de blocage (catégorie métier uniquement)
    blocking_duration_bucket = models.CharField(
        max_length=30,
        choices=BlockingDurationBucket.choices,
        null=True,
        blank=True,
        verbose_name=_("durée du blocage"),
    )

    source = models.CharField(
        max_length=30,
        choices=LeadSource.choices,
        default=LeadSource.WEBSITE,
        verbose_name=_("source"),
    )

    # 📊 Tracking
    created_at = models.DateTimeField(default=timezone.now, verbose_name=_("date de création"))

    status = models.ForeignKey(
        "lead_status.LeadStatus",
        on_delete=models.PROTECT,
        verbose_name=_("statut"),
    )

    assigned_to = models.ManyToManyField(
        "users.User",
        blank=True,
        verbose_name=_("assignés à"),
    )

    jurist_assigned = models.ManyToManyField(
        "users.User",
        blank=True,
        related_name="leads_juriste",
        verbose_name=_("juristes assignés"),
    )

    juriste_assigned_at = models.DateTimeField(null=True, blank=True)

    # ⚙️ Meta
    class Meta:
        verbose_name = _("lead")
        verbose_name_plural = _("leads")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"], name="lead_status_idx"),
            models.Index(fields=["appointment_date"], name="lead_appointment_idx"),
            models.Index(fields=["created_at"], name="lead_created_idx"),
            models.Index(fields=["service"], name="lead_service_idx"),
            models.Index(fields=["department_code"], name="lead_department_idx"),
            models.Index(fields=["source"], name="lead_source_idx"),
            models.Index(fields=["blocking_duration_bucket"], name="lead_blocking_bucket_idx"),
        ]

    # 🧠 Validation
    def clean(self):
        if self.department_code and not self.department_code.isdigit():
            raise ValidationError({"department_code": _("Le code département doit être numérique")})

    # 🖨️ Display
    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.status.label if self.status else _('Sans statut')}"

    # 💾 Logique métier
    def save(self, *args, **kwargs):
        # Statut par défaut
        if not self.status:
            try:
                default_status = LeadStatus.objects.get(code=RDV_PLANIFIE)
                self.status = default_status
            except LeadStatus.DoesNotExist:
                pass

        # Si RDV défini → statut confirmé
        if self.appointment_date:
            try:
                confirmed_status = LeadStatus.objects.get(code=RDV_CONFIRME)
                self.status = confirmed_status
            except LeadStatus.DoesNotExist:
                pass

        super().save(*args, **kwargs)

    # 🔥 Helper métier
    @property
    def is_hot(self):
        if self.is_urgent:
            return True

        if self.blocking_duration_bucket in [
            BlockingDurationBucket.THREE_TO_SIX_MONTHS,
            BlockingDurationBucket.SIX_TO_TWELVE_MONTHS,
            BlockingDurationBucket.MORE_THAN_ONE_YEAR,
        ]:
            return True

        return False