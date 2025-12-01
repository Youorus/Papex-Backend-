# tasks.py

from celery import shared_task

from api.jurist_appointment.models import JuristAppointment
from api.leads.models import Lead
from api.users.models import User
from api.utils.email.jurist_appointment.notifications import (
    send_jurist_appointment_deleted_email,
    send_jurist_appointment_email,
)


@shared_task
def send_jurist_appointment_created_task(appointment_id):
    """
    Envoie un e-mail de confirmation de rendez-vous juriste.
    """
    try:
        appointment = JuristAppointment.objects.select_related("lead").get(
            id=appointment_id
        )
        send_jurist_appointment_email(appointment)
    except JuristAppointment.DoesNotExist:
        # Optionnel : log si besoin
        print(f"❌ JuristAppointment #{appointment_id} introuvable.")


@shared_task
def send_jurist_appointment_deleted_task(lead_id, jurist_id, date_str):
    """
    Envoie un e-mail d’annulation de rendez-vous juriste.
    """
    from datetime import datetime

    try:
        lead = Lead.objects.get(id=lead_id)
        jurist = User.objects.get(id=jurist_id)
        date = datetime.fromisoformat(date_str)
        send_jurist_appointment_deleted_email(lead, jurist, date)
    except (Lead.DoesNotExist, User.DoesNotExist, ValueError) as e:
        print(f"❌ Erreur d’envoi email annulation rendez-vous juriste : {e}")
