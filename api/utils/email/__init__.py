# api/utils/email/__init__.py
from .config import send_html_email
from .leads.notifications import (
    send_appointment_confirmation_email,
    send_appointment_reminder_email,
    send_missed_appointment_email,
)
