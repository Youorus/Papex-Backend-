# leads/constants.py
"""
Constantes centralisées pour le module Leads.

Objectifs :
- Éviter les strings en dur dans le code
- Faciliter la maintenance et la lisibilité
- Permettre l’import global dans toute l’application
"""
from django.db import models
from django.utils.translation import gettext_lazy as _


# =========================================================
# 📊 STATUTS LEAD (codes métier)
# =========================================================

RDV_A_CONFIRMER = "RDV_A_CONFIRMER"
RDV_CONFIRME = "RDV_CONFIRME"
RDV_PLANIFIE = "RDV_PLANIFIE"  # legacy / optionnel
A_RAPPELER = "A_RAPPELER"
ABSENT = "ABSENT"
PRESENT = "PRESENT"

# Liste globale utilisable pour validations ou seeds
LEAD_STATUS_CODES = [
    RDV_A_CONFIRMER,
    A_RAPPELER,
    RDV_CONFIRME,
    RDV_PLANIFIE,
    ABSENT,
    PRESENT,
]


# =========================================================
# 📅 TYPES DE RENDEZ-VOUS
# =========================================================

RDV_PRESENTIEL = "PRESENTIEL"
RDV_TELEPHONE = "TELEPHONE"
RDV_VISIO_CONFERENCE = "VISIO_CONFERENCE"

APPOINTMENT_TYPE_CHOICES = [
    (RDV_PRESENTIEL, _("Présentiel")),
    (RDV_TELEPHONE, _("Téléphonique")),
    (RDV_VISIO_CONFERENCE, _("Visio-conférence")),
]


# =========================================================
# 📣 SOURCES D’ACQUISITION LEAD
# =========================================================

class LeadSource(models.TextChoices):
    """
    Enum des sources d'acquisition marketing et commerciales.

    Permet :
    - tracking marketing
    - reporting
    - segmentation CRM
    """

    # 🌐 Web & recherche
    WEBSITE = "WEBSITE", _("Site internet")
    LANDING_PAGE = "LANDING_PAGE", _("Landing page")
    GOOGLE_SEARCH = "GOOGLE_SEARCH", _("Recherche Google")
    GOOGLE_ADS = "GOOGLE_ADS", _("Publicité Google Ads")
    SEO = "SEO", _("Résultat naturel (SEO)")

    # 📱 Réseaux sociaux (organique)
    FACEBOOK = "FACEBOOK", _("Facebook")
    INSTAGRAM = "INSTAGRAM", _("Instagram")
    TIKTOK = "TIKTOK", _("TikTok")
    LINKEDIN = "LINKEDIN", _("LinkedIn")
    YOUTUBE = "YOUTUBE", _("YouTube")
    TWITTER = "TWITTER", _("Twitter / X")

    # 🎥 Lives
    TIKTOK_LIVE = "TIKTOK_LIVE", _("Live TikTok")
    FACEBOOK_LIVE = "FACEBOOK_LIVE", _("Live Facebook")
    INSTAGRAM_LIVE = "INSTAGRAM_LIVE", _("Live Instagram")
    YOUTUBE_LIVE = "YOUTUBE_LIVE", _("Live YouTube")

    # 💰 Publicités Social Ads
    FACEBOOK_ADS = "FACEBOOK_ADS", _("Publicité Facebook")
    INSTAGRAM_ADS = "INSTAGRAM_ADS", _("Publicité Instagram")
    TIKTOK_ADS = "TIKTOK_ADS", _("Publicité TikTok")
    LINKEDIN_ADS = "LINKEDIN_ADS", _("Publicité LinkedIn")

    # 🗣️ Recommandations
    WORD_OF_MOUTH = "WORD_OF_MOUTH", _("Bouche à oreille")
    REFERRAL_CLIENT = "REFERRAL_CLIENT", _("Recommandation client")
    REFERRAL_PARTNER = "REFERRAL_PARTNER", _("Recommandation partenaire")
    FRIEND_FAMILY = "FRIEND_FAMILY", _("Proche / famille")

    # 🤝 Partenariats
    PARTNER = "PARTNER", _("Partenaire")
    ASSOCIATION = "ASSOCIATION", _("Association")
    LAWYER = "LAWYER", _("Avocat")
    ACCOUNTANT = "ACCOUNTANT", _("Comptable")

    # 🏢 Offline / physique
    BUSINESS_CARD = "BUSINESS_CARD", _("Carte de visite")
    STREET_POSTER = "STREET_POSTER", _("Affiche dans la rue")
    FLYER = "FLYER", _("Flyer")
    OFFICE_WALKIN = "OFFICE_WALKIN", _("Passage en agence")
    EVENT = "EVENT", _("Événement / salon")

    # 📞 Contact direct
    COLD_CALL = "COLD_CALL", _("Appel sortant")
    INBOUND_CALL = "INBOUND_CALL", _("Appel entrant")
    SMS = "SMS", _("SMS")
    EMAIL = "EMAIL", _("Email")

    # 📰 Contenu & médias
    BLOG = "BLOG", _("Article de blog")
    PRESS = "PRESS", _("Article presse")
    PODCAST = "PODCAST", _("Podcast")
    WEBINAR = "WEBINAR", _("Webinaire")

    # ❓ Autre
    OTHER = "OTHER", _("Autre")


class BlockingDurationBucket(models.TextChoices):
    LESS_THAN_1_MONTH = "LESS_THAN_1_MONTH", _("Moins d’1 mois")
    ONE_TO_THREE_MONTHS = "ONE_TO_THREE_MONTHS", _("1 à 3 mois")
    THREE_TO_SIX_MONTHS = "THREE_TO_SIX_MONTHS", _("3 à 6 mois")
    SIX_TO_TWELVE_MONTHS = "SIX_TO_TWELVE_MONTHS", _("6 à 12 mois")
    MORE_THAN_ONE_YEAR = "MORE_THAN_ONE_YEAR", _("Plus d’un an")