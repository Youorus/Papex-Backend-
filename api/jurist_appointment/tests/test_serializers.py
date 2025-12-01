from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from api.jurist_appointment.models import JuristAppointment
from api.jurist_appointment.serializers import (
    JuristAppointmentCreateSerializer,
    JuristAppointmentSerializer,
)
from api.leads.models import Lead
from api.users.models import User
from api.users.roles import UserRoles

pytestmark = pytest.mark.django_db


def create_jurist():
    return User.objects.create_user(
        email="juriste@example.com",
        password="testpass",
        first_name="Marie",
        last_name="Curie",
        role=UserRoles.JURISTE,
    )


def create_lead():
    from api.lead_status.models import LeadStatus

    status = LeadStatus.objects.first() or LeadStatus.objects.create(
        code="NOUVEAU", label="Nouveau", color="#000000"
    )
    return Lead.objects.create(
        first_name="Jean",
        last_name="Dupont",
        email="jean.dupont@example.com",
        status=status,
    )


def test_valid_jurist_appointment_create_serializer():
    jurist = create_jurist()
    lead = create_lead()
    date = timezone.now() + timedelta(days=1)

    serializer = JuristAppointmentCreateSerializer(
        data={"lead": lead.id, "jurist": jurist.id, "date": date.isoformat()}
    )

    assert serializer.is_valid(), serializer.errors
    instance = serializer.save()
    assert instance.lead == lead
    assert instance.jurist == jurist
    assert instance.date == date


def test_invalid_duplicate_slot_for_jurist():
    jurist = create_jurist()
    lead1 = create_lead()
    from api.lead_status.models import LeadStatus

    status = LeadStatus.objects.first() or LeadStatus.objects.create(
        code="NOUVEAU", label="Nouveau", color="#000000"
    )
    lead2 = Lead.objects.create(
        first_name="Lucie",
        last_name="Martin",
        email="lucie.martin@example.com",
        status=status,
    )
    date = timezone.now() + timedelta(days=1)

    JuristAppointment.objects.create(jurist=jurist, lead=lead1, date=date)

    serializer = JuristAppointmentCreateSerializer(
        data={"lead": lead2.id, "jurist": jurist.id, "date": date.isoformat()}
    )

    assert not serializer.is_valid()
    assert "non_field_errors" in serializer.errors
    assert (
        "doivent former un ensemble unique"
        in serializer.errors["non_field_errors"][0].lower()
    )


def test_invalid_lead_has_already_appointment_that_day():
    jurist1 = create_jurist()
    jurist2 = User.objects.create_user(
        email="juriste2@example.com",
        password="testpass",
        first_name="Paul",
        last_name="Durand",
        role=UserRoles.JURISTE,
    )
    lead = create_lead()
    date = timezone.now() + timedelta(days=2)

    JuristAppointment.objects.create(jurist=jurist1, lead=lead, date=date)

    serializer = JuristAppointmentCreateSerializer(
        data={
            "lead": lead.id,
            "jurist": jurist2.id,
            "date": date.replace(hour=16).isoformat(),
        }
    )

    assert not serializer.is_valid()
    assert "non_field_errors" in serializer.errors
    assert "ce lead a déjà" in serializer.errors["non_field_errors"][0].lower()


def test_jurist_appointment_serializer_output():
    jurist = create_jurist()
    lead = create_lead()
    date = timezone.now() + timedelta(days=1)

    appointment = JuristAppointment.objects.create(lead=lead, jurist=jurist, date=date)

    serializer = JuristAppointmentSerializer(instance=appointment)
    data = serializer.data

    assert data["lead"]["id"] == str(lead.id)
    assert data["jurist"]["id"] == str(jurist.id)
    assert "date" in data
    assert "created_at" in data
