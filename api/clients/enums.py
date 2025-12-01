from django.db import models
from django.utils.translation import gettext_lazy as _


class SourceInformation(models.TextChoices):
    GOOGLE = "GOOGLE", _("Google")
    FACEBOOK = "FACEBOOK", _("Facebook")
    INSTAGRAM = "INSTAGRAM", _("Instagram")
    TIKTOK = "TIKTOK", _("Tiktok")
    PASSAGE = "PASSAGE", _("Passage")
    PUB_METRO = "PUB_METRO", _("Pub métro")
    BOUCHE_OREILLE = "BOUCHE_OREILLE", _("Bouche à oreille")
    FLYERS = "FLYERS", _("Flyers")
    TV = "TV", _("TV")
    RADIO = "RADIO", _("Radio")
    AUTRES = "AUTRES", _("Autres (précisez)")


class Civilite(models.TextChoices):
    MADAME = "MADAME", _("Madame")
    MADEMOISELLE = "MADEMOISELLE", _("Mademoiselle")
    MONSIEUR = "MONSIEUR", _("Monsieur")


class VisaType(models.TextChoices):
    SCHENGEN = "SCHENGEN", _("Visa Schengen")
    LONG_SEJOUR = "LONG_SEJOUR", _("Visa long séjour")
    ETUDIANT = "ETUDIANT", _("Visa étudiant")
    VLS_TS = "VLS_TS", _("VLS-TS")
    AUTRE = "AUTRE", _("Autre")


class SituationFamiliale(models.TextChoices):
    CELIBATAIRE = "CELIBATAIRE", _("Célibataire")
    MARIE = "MARIE", _("Marié(e)")
    CONCUBIN = "CONCUBIN", _("Concubin(e)")
    DIVORCE = "DIVORCE", _("Divorcé(e)")
    VEUF = "VEUF", _("Veuf(ve)")


class LogementType(models.TextChoices):
    LOCATAIRE = "LOCATAIRE", _("Locataire")
    PROPRIETAIRE = "PROPRIETAIRE", _("Propriétaire")
    HEBERGE = "HEBERGE", _("Hébergé")
    AUTRE = "AUTRE", _("Autre")


class SituationProfessionnelle(models.TextChoices):
    CDI = "CDI", _("En CDI")
    CDD_INTERIM = "CDD_INTERIM", _("En CDD / Intérim")
    INDEPENDANT = "INDEPENDANT", _("Profession libérale / Indépendant")
    ETUDIANT = "ETUDIANT", _("Étudiant")
    SANS_EMPLOI = "SANS_EMPLOI", _("Sans emploi")
