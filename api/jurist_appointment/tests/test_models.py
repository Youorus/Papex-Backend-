from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from api.jurist_appointment.models import JuristAppointment
from api.lead_status.models import LeadStatus
from api.leads.models import Lead
from api.users.models import User
from api.users.roles import UserRoles

pytestmark = pytest.mark.django_db


def create_jurist():
    return User.objects.create_user(
        email="juriste@example.com",
        password="password123",
        first_name="Marie",
        last_name="Curie",
        role=UserRoles.JURISTE,
    )


def create_lead():
    status = LeadStatus.objects.first() or LeadStatus.objects.create(
        code="INCOMPLET", label="Incomplet", color="gray"
    )
    return Lead.objects.create(
        first_name="Jean",
        last_name="Dupont",
        email="jean.dupont@example.com",
        status=status,
    )


def test_jurist_appointment_str():
    jurist = create_jurist()
    lead = create_lead()
    date = timezone.now() + timedelta(days=2)
    appointment = JuristAppointment.objects.create(lead=lead, jurist=jurist, date=date)
    assert (
        str(appointment) == f"{lead} avec {jurist} le {date.strftime('%d/%m/%Y %H:%M')}"
    )


def test_jurist_appointment_unique_constraint():
    """
    On ne peut pas créer deux rendez-vous avec le même juriste à la même date.
    """
    jurist = create_jurist()
    lead1 = create_lead()
    status = LeadStatus.objects.first()
    lead2 = Lead.objects.create(
        first_name="Lucie",
        last_name="Martin",
        email="lucie.martin@example.com",
        status=status,
    )
    date = timezone.now() + timedelta(days=1)

    JuristAppointment.objects.create(lead=lead1, jurist=jurist, date=date)

    with pytest.raises(Exception) as exc_info:
        JuristAppointment.objects.create(lead=lead2, jurist=jurist, date=date)

    assert "UNIQUE constraint failed" in str(exc_info.value) or "duplicate key" in str(
        exc_info.value
    )
