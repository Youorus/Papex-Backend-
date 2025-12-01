# api/utils/email/leads/daily_report.py
import os
from django.core.mail import EmailMessage
from django.conf import settings

from api.utils.email.leads.pdf_report.appointment_report import generate_daily_appointment_report


def send_daily_appointment_report(leads):
    """
    Envoie par e-mail le PDF des rendez-vous du jour.
    """
    if not leads:
        return None

    recipient = os.getenv("DAILY_RDV_REPORT_EMAIL") or settings.DEFAULT_FROM_EMAIL
    pdf_buffer = generate_daily_appointment_report(leads)

    subject = "📋 Rapport quotidien des rendez-vous – TDS France"
    body = (
        "Bonjour,\n\n"
        "Veuillez trouver ci-joint le rapport complet des rendez-vous planifiés ou confirmés pour aujourd'hui.\n\n"
        "Bien cordialement,\n"
        "Équipe TDS France"
    )

    email = EmailMessage(
        subject=subject,
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient],
    )

    email.attach(
        filename=f"rapport_rdv_{leads[0].appointment_date.date()}.pdf",
        content=pdf_buffer.getvalue(),
        mimetype="application/pdf",
    )

    email.send(fail_silently=False)
    return recipient