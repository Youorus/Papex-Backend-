from django.db import models
from django.db.models import JSONField
from django.utils.translation import gettext_lazy as _
from django.utils.text import slugify


class Job(models.Model):
    """
    Modèle représentant une offre d'emploi chez Papiers Express.
    Contient toutes les informations nécessaires pour afficher une fiche de poste complète.
    """

    # Identifiant unique (slug généré automatiquement)
    slug = models.SlugField(
        _("identifiant unique"),
        max_length=255,
        unique=True,
        blank=True,
        help_text=_("Généré automatiquement à partir du titre")
    )

    # Informations principales
    title = models.CharField(
        _("titre du poste"),
        max_length=255,
        help_text=_("Ex: Assistant(e) administratif(ve)")
    )

    location = models.CharField(
        _("lieu de travail"),
        max_length=255,
        help_text=_("Ex: Paris 17e, Paris / Hybride")
    )

    type = models.CharField(
        _("type de contrat"),
        max_length=100,
        help_text=_("Ex: CDI – Temps plein, CDD – 6 mois, Stage")
    )

    # Description
    description = models.TextField(
        _("description courte"),
        help_text=_("Résumé affiché dans la liste des offres (2-3 lignes)")
    )

    # Listes (stockées en JSON)
    missions = JSONField(
        _("missions principales"),
        default=list,
        blank=True,
        help_text=_("Liste des responsabilités et tâches du poste")
    )

    profile = JSONField(
        _("profil recherché"),
        default=list,
        blank=True,
        help_text=_("Liste des compétences et qualifications requises")
    )

    # Informations complémentaires
    diploma = models.CharField(
        _("diplôme requis"),
        max_length=255,
        blank=True,
        help_text=_("Ex: Bac +2 minimum, Bac +3 en Droit")
    )

    start_date = models.CharField(
        _("date de début souhaitée"),
        max_length=100,
        blank=True,
        help_text=_("Ex: Dès que possible, Janvier 2025 (optionnel)")
    )

    # Statut de publication
    is_active = models.BooleanField(
        _("offre active"),
        default=True,
        help_text=_("Décocher pour désactiver l'offre sans la supprimer")
    )

    # Timestamps
    created_at = models.DateTimeField(_("créé le"), auto_now_add=True)
    updated_at = models.DateTimeField(_("modifié le"), auto_now=True)

    class Meta:
        verbose_name = _("offre d'emploi")
        verbose_name_plural = _("offres d'emploi")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(fields=["slug"]),
        ]

    def __str__(self):
        """
        Représentation lisible de l'offre d'emploi.
        """
        status = "✅" if self.is_active else "❌"
        return f"{status} {self.title} - {self.type}"

    def save(self, *args, **kwargs):
        """
        Génère automatiquement le slug à partir du titre si non fourni.
        """
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1

            while Job.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            self.slug = slug

        super().save(*args, **kwargs)

    def get_absolute_url(self):
        """
        Retourne l'URL de la fiche de poste.
        """
        return f"/recrutement/{self.slug}"

    @property
    def is_published(self):
        """
        Vérifie si l'offre est publiée et visible.
        """
        return self.is_active