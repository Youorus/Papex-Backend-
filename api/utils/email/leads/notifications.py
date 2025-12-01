import os
from datetime import datetime
from urllib.parse import quote_plus
from django.conf import settings
from api.utils.email import send_html_email
from slugify import slugify
from api.utils.email.config import TDS_FRANCE_ADDRESS, _build_context


def send_appointment_planned_email(lead):
    """
    Envoie un e-mail au lead pour l’informer que son rendez-vous a été planifié.
    """
    context = _build_context(lead, lead.appointment_date, TDS_FRANCE_ADDRESS)
    return send_html_email(
        to_email=lead.email,
        subject="Planification confirmée : votre rendez-vous avec TDS France",
        template_name="email/leads/appointment_planned.html",
        context=context,
    )


def send_appointment_confirmation_email(lead):
    """
    Envoie un e-mail de confirmation au lead pour son rendez-vous chez TDS France.
    """
    context = _build_context(lead, lead.appointment_date, TDS_FRANCE_ADDRESS)
    return send_html_email(
        to_email=lead.email,
        subject="Confirmation officielle : rendez-vous validé avec TDS France",
        template_name="email/leads/appointment_confirmed.html",
        context=context,
    )


def send_appointment_reminder_email(lead):
    """
    Envoie un e-mail de rappel au lead avant son rendez-vous.
    """
    context = _build_context(lead, lead.appointment_date, TDS_FRANCE_ADDRESS)
    return send_html_email(
        to_email=lead.email,
        subject="Rappel important : votre rendez-vous approche – TDS France",
        template_name="email/leads/appointment_reminder.html",
        context=context,
    )


def send_missed_appointment_email(lead):
    """
    Envoie un e-mail au lead pour l’informer qu’il a manqué son rendez-vous.
    """
    context = _build_context(lead, lead.appointment_date, TDS_FRANCE_ADDRESS)
    return send_html_email(
        to_email=lead.email,
        subject="Absence constatée à votre rendez-vous – TDS France",
        template_name="email/leads/appointment_absent.html",
        context=context,
    )


def send_formulaire_email(lead):
    """
    Envoie un e-mail contenant un lien vers le formulaire à compléter par le lead.
    Inclut le prénom, le nom et l’identifiant du lead dans l’URL.
    """
    if not lead.email:
        print(f"[WARNING] Aucun email pour le lead {lead.id}")
        return

    name_slug = slugify(f"{lead.first_name}-{lead.last_name}")
    formulaire_url = f"{settings.FRONTEND_URL}/formulaire?id={lead.id}&name={name_slug}"

    context = _build_context(
        lead,
        extra={
            "formulaire_url": formulaire_url,
        },
    )

    return send_html_email(
        to_email=lead.email,
        subject="Formulaire à compléter pour finaliser votre dossier – TDS France",
        template_name="email/leads/formulaire_link.html",
        context=context,
    )


def send_dossier_status_email(lead):
    """
    Envoie un e-mail au lead pour l’informer d’un changement de statut de dossier.

    Conditions :
    - L’e-mail du lead doit être renseigné.
    - Le statut de dossier (`statut_dossier`) doit être défini.

    L’email contient :
    - Le prénom et nom du lead
    - Le code, le label et la couleur du statut de dossier
    - Un lien ou un contact de suivi
    """
    if not lead.email or not lead.statut_dossier:
        return

    context = _build_context(
        lead,
        extra={
            "statut_dossier": lead.statut_dossier,
        },
    )

    return send_html_email(
        to_email=lead.email,
        subject="Mise à jour : évolution du statut de votre dossier – TDS France",
        template_name="email/leads/dossier_status_update.html",
        context=context,
    )


def send_jurist_assigned_email(lead, jurist):
    """
    Envoie un e-mail au lead pour l’informer qu’un juriste lui a été assigné.
    """
    context = _build_context(
        lead,
        extra={
            "jurist": jurist,
        },
    )

    return send_html_email(
        to_email=lead.email,
        subject="Votre dossier est désormais suivi par un juriste dédié – TDS France",
        template_name="email/leads/jurist_assigned.html",
        context=context,
    )