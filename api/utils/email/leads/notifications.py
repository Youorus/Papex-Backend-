from django.conf import settings
from slugify import slugify

from api.utils.email import send_html_email
from api.utils.email.config import _build_context, COMPANY_ADDRESS


# ================================================================
# RDV
# ================================================================

def send_appointment_planned_email(lead):
    context = _build_context(
        lead,
        dt=lead.appointment_date,
        location=COMPANY_ADDRESS,
    )

    return send_html_email(
        to_email=lead.email,
        subject="Planification confirmée : votre rendez-vous avec Papiers Express",
        template_name="email/leads/appointment_planned.html",
        context=context,
    )


def send_appointment_confirmation_email(lead):
    context = _build_context(
        lead,
        dt=lead.appointment_date,
        location=None,
    )

    return send_html_email(
        to_email=lead.email,
        subject="Confirmation officielle : rendez-vous validé avec Papiers Express",
        template_name="email/leads/appointment_confirmed.html",
        context=context,
    )


def send_appointment_reminder_email(lead):
    context = _build_context(
        lead,
        dt=lead.appointment_date,
        location=None,
    )

    return send_html_email(
        to_email=lead.email,
        subject="Rappel important : votre rendez-vous approche – Papiers Express",
        template_name="email/leads/appointment_reminder.html",
        context=context,
    )


def send_appointment_absent_email(lead):
    context = _build_context(
        lead,
        dt=lead.appointment_date,
        location=None,
    )

    return send_html_email(
        to_email=lead.email,
        subject="Vous avez manqué votre rendez-vous - Papiers Express",
        template_name="email/leads/appointment_absent.html",
        context=context,
    )


# ================================================================
# FORMULAIRE
# ================================================================

def send_formulaire_email(lead):
    if not lead.email:
        return

    name_slug = slugify(f"{lead.first_name}-{lead.last_name}")

    formulaire_url = (
        f"{settings.FRONTEND_URL}/formulaire?"
        f"id={lead.id}&name={name_slug}"
    )

    context = _build_context(
        lead,
        extra={"formulaire_url": formulaire_url},
    )

    return send_html_email(
        to_email=lead.email,
        subject="Formulaire à compléter pour finaliser votre dossier – Papiers Express",
        template_name="email/leads/formulaire_link.html",
        context=context,
    )


# ================================================================
# DOSSIER
# ================================================================

def send_dossier_status_email(lead):
    if not lead.email or not lead.statut_dossier:
        return

    context = _build_context(
        lead,
        extra={"statut_dossier": lead.statut_dossier},
    )

    return send_html_email(
        to_email=lead.email,
        subject="Mise à jour : évolution du statut de votre dossier – Papiers Express",
        template_name="email/leads/dossier_status_update.html",
        context=context,
    )


# ================================================================
# JURISTE
# ================================================================

def send_jurist_assigned_email(lead, jurist):
    context = _build_context(
        lead,
        extra={"jurist": jurist},
    )

    return send_html_email(
        to_email=lead.email,
        subject="Votre dossier est désormais suivi par un juriste dédié – Papiers Express",
        template_name="email/leads/jurist_assigned.html",
        context=context,
    )