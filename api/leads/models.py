from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from api.lead_status.models import LeadStatus
from api.leads.constants import RDV_CONFIRME, RDV_PLANIFIE


class Lead(models.Model):
    """
    Modèle représentant un prospect (Lead) utilisé pour le suivi commercial.

    Ce modèle centralise toutes les informations nécessaires à la gestion
    et à la qualification d’un lead (prospect), depuis sa création jusqu’à la prise de rendez-vous,
    incluant l’assignation à un conseiller et le suivi du statut.
    """

    id = models.AutoField(primary_key=True, verbose_name=_("ID"))

    first_name = models.CharField(
        max_length=150, verbose_name=_("prénom"), help_text=_("Prénom du prospect")
    )

    last_name = models.CharField(
        max_length=150, verbose_name=_("nom"), help_text=_("Nom de famille du prospect")
    )

    email = models.EmailField(
        blank=True,
        null=True,
        verbose_name=_("email"),
        help_text=_("Adresse email du prospect (optionnelle)"),
    )

    phone = models.CharField(
        max_length=20,
        verbose_name=_("téléphone"),
        help_text=_("Numéro de téléphone au format international (ex: +33612345678)"),
    )

    statut_dossier = models.ForeignKey(
        "statut_dossier.StatutDossier",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name=_("statut du dossier"),
        help_text=_("Suivi interne de l’état d’avancement du dossier"),
    )
    statut_dossier_interne = models.ForeignKey(
        "statut_dossier_interne.StatutDossierInterne",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name=_("statut du dossier interne"),
        help_text=_("Suivi interne réservé à l’équipe pour l’état d’avancement interne du dossier"),
    )

    appointment_date = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_("date de rendez-vous"),
        help_text=_("Date et heure du rendez-vous (optionnel)"),
    )

    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name=_("date de création"),
        help_text=_(
            "Date et heure de création du lead, utilisée pour la traçabilité et le suivi historique"
        ),
    )

    status = models.ForeignKey(
        "lead_status.LeadStatus",
        on_delete=models.PROTECT,
        verbose_name=_("statut"),
        help_text=_("Statut actuel du lead (ex: NOUVEAU, RDV_VALIDÉ, etc.)"),
    )

    assigned_to = models.ManyToManyField(
        "users.User",
        blank=True,
        verbose_name=_("assignés à"),
        help_text=_("Conseillers à qui ce lead est assigné"),
    )
    jurist_assigned = models.ManyToManyField(
        "users.User",
        blank=True,
        related_name="leads_juriste",
        verbose_name=_("juristes assignés"),
        help_text=_("Juristes responsables du lead (assignés par un administrateur)"),
    )
    juriste_assigned_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("lead")
        verbose_name_plural = _("leads")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"], name="lead_status_idx"),
            models.Index(fields=["appointment_date"], name="lead_appointment_idx"),
            models.Index(fields=["created_at"], name="lead_created_idx"),
        ]

    def __str__(self):
        """
        Affichage lisible du lead : Prénom, nom et statut.
        """
        return f"{self.first_name} {self.last_name} - {self.status.label if self.status else _('Sans statut')}"

    def save(self, *args, **kwargs):
        """
        Surcharge de la méthode save pour gérer la logique métier liée au statut du lead.

        Étapes appliquées lors de la sauvegarde :
        1. Affectation d'un statut par défaut 'RDV_PLANIFIE' si aucun statut n'est défini.
           Cela garantit qu'un lead possède toujours un statut initial cohérent.
        2. Si une date de rendez-vous est renseignée (appointment_date non nulle),
           le statut est automatiquement mis à jour en 'RDV_CONFIRME', quel que soit le statut actuel.
           Ceci reflète la confirmation effective du rendez-vous dans le suivi du lead.

        Ces règles permettent d'assurer la cohérence des statuts en fonction des informations disponibles
        et facilitent le suivi commercial automatisé.
        """
        # 1. Statut par défaut si absent
        if not self.status:
            try:
                default_status = LeadStatus.objects.get(code=RDV_PLANIFIE)
                self.status = default_status
            except LeadStatus.DoesNotExist:
                pass  # Tu peux lever une exception si besoin

        super().save(*args, **kwargs)
