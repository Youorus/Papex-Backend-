from django.db import models
from django.db.models import JSONField
from django.utils.translation import gettext_lazy as _

from api.clients.enums import (
    Civilite,
    LogementType,
    SituationFamiliale,
    SituationProfessionnelle,
    VisaType,
)


class Client(models.Model):
    """
    Modèle représentant les données détaillées d'un client (liées à un Lead).
    Centralise toutes les informations d’état civil, demande, famille, et situation professionnelle.
    """

    # Lien vers le lead principal
    lead = models.OneToOneField(
        "leads.Lead",
        on_delete=models.CASCADE,
        related_name="form_data",
        verbose_name=_("lead"),
    )

    has_anef_account = models.BooleanField(
        _("a un compte ANEF ?"), null=True, blank=True
    )
    anef_email = models.CharField(
        _("email du compte ANEF (texte libre)"),
        max_length=255,
        blank=True
    )
    anef_password = models.CharField(
        _("mot de passe du compte ANEF"), max_length=255, blank=True
    )

    # Compte Démarches Simplifiées
    has_demarche_simplifiee_account = models.BooleanField(
        _("a un compte Démarches Simplifiées ?"), null=True, blank=True
    )
    demarche_simplifiee_email = models.CharField(
        _("email du compte Démarches Simplifiées (texte libre)"),
        max_length=255,
        blank=True
    )
    demarche_simplifiee_password = models.CharField(
        _("mot de passe du compte Démarches Simplifiées"),
        max_length=255,
        blank=True
    )

    # Source(s) d'information (enum JSON, liste)
    source = JSONField(blank=True, default=list, verbose_name=_("source d'information"))

    # État civil
    civilite = models.CharField(
        _("civilité"), max_length=15, choices=Civilite.choices, blank=True
    )
    date_naissance = models.DateField(_("date de naissance"), blank=True, null=True)
    lieu_naissance = models.CharField(
        _("lieu de naissance"), max_length=255, blank=True
    )
    pays = models.CharField(_("pays"), max_length=100, blank=True)
    nationalite = models.CharField(_("nationalité"), max_length=100, blank=True)

    # Adresse
    adresse = models.CharField(_("adresse"), max_length=255, blank=True)
    code_postal = models.CharField(_("code postal"), max_length=20, blank=True)
    ville = models.CharField(_("ville"), max_length=100, blank=True)
    date_entree_france = models.DateField(
        _("date d’entrée en France"), blank=True, null=True
    )

    # Demande
    type_demande = models.ForeignKey(
        "services.Service", on_delete=models.PROTECT, null=True, blank=True
    )

    custom_demande = models.CharField(
        _("autre demande (à préciser)"),
        max_length=255,
        blank=True,
        default="",
        help_text=_('À remplir si le service choisi est "Autre"'),
    )
    demande_deja_formulee = models.BooleanField(
        _("demande déjà formulée ?"), null=True, blank=True
    )
    demande_formulee_precise = models.CharField(
        _("si oui, laquelle ?"), max_length=255, blank=True
    )

    # Visa
    a_un_visa = models.BooleanField(_("visa"), null=True, blank=True)
    type_visa = models.CharField(
        _("type de visa"),
        max_length=20,
        choices=VisaType.choices,
        null=True,
        blank=True,
    )
    date_expiration_visa = models.DateField(
        _("date d'expiration du visa"), null=True, blank=True
    )
    statut_refugie_ou_protection = models.BooleanField(
        _("statut réfugié ou protection subsidiaire"), null=True, blank=True
    )

    # Situation familiale
    situation_familiale = models.CharField(
        _("situation familiale"),
        max_length=20,
        choices=SituationFamiliale.choices,
        blank=True,
    )
    a_des_enfants = models.BooleanField(_("a des enfants ?"), null=True, blank=True)
    nombre_enfants = models.PositiveIntegerField(
        _("nombre d’enfants"), blank=True, null=True
    )
    nombre_enfants_francais = models.PositiveIntegerField(
        _("nombre d’enfants français"), blank=True, null=True
    )
    enfants_scolarises = models.BooleanField(
        _("enfants scolarisés ?"), null=True, blank=True
    )
    naissance_enfants_details = models.TextField(
        _("détails naissance enfants"), blank=True
    )

    # Situation professionnelle
    situation_pro = models.CharField(
        _("situation professionnelle"),
        max_length=30,
        choices=SituationProfessionnelle.choices,
        blank=True,
    )
    domaine_activite = models.CharField(
        _("domaine d’activité"), max_length=255, blank=True
    )
    nombre_fiches_paie = models.PositiveIntegerField(
        _("nombre de fiches de paie"), blank=True, null=True
    )
    date_depuis_sans_emploi = models.DateField(
        _("depuis quelle date sans emploi / étudiant"), blank=True, null=True
    )

    # Logement
    logement_type = models.CharField(
        _("type de logement"), max_length=20, choices=LogementType.choices, blank=True
    )

    # OQTF et démarches administratives
    a_deja_eu_oqtf = models.BooleanField(_("déjà eu une OQTF ?"), null=True, blank=True)
    date_derniere_oqtf = models.DateField(
        _("date de la dernière OQTF"), null=True, blank=True
    )
    demarche_en_cours_administration = models.BooleanField(
        _("démarche en cours auprès de l’administration ?"), null=True, blank=True
    )

    # Remarques libres
    remarques = models.TextField(_("remarques"), blank=True)

    # Timestamps
    created_at = models.DateTimeField(_("créé le"), auto_now_add=True)
    updated_at = models.DateTimeField(_("modifié le"), auto_now=True)

    class Meta:
        verbose_name = _("données client")
        verbose_name_plural = _("données clients")
        ordering = ["-created_at"]

    def __str__(self):
        """
        Représentation lisible du client, affichée dans l’admin Django.
        """
        return f"Données de {self.lead.first_name} {self.lead.last_name}"
