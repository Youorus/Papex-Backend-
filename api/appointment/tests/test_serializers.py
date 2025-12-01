# api/appointment/test_serializers.py

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from api.appointment.models import Appointment
from api.appointment.serializers import AppointmentSerializer
from api.leads.models import Lead
from api.users.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return User.objects.create_user(
        email="conseiller@example.com",
        password="testpassword",
        role="CONSEILLER",
        first_name="Jean",
        last_name="Dupont",
    )


@pytest.fixture
def lead(user):
    from api.leads.models import LeadStatus

    lead = Lead.objects.create(
        first_name="Alice",
        last_name="Martin",
        email="alice@example.com",
        phone="+33600000000",
        status=LeadStatus.objects.get_or_create(
            code="RDV_PLANIFIE", defaults={"label": "Planifié", "color": "#000000"}
        )[0],
    )
    lead.assigned_to.set([user])
    return lead


def test_valid_appointment_serializer(lead, user):
    """
    Vérifie que le serializer accepte des données valides.
    """
    future_date = timezone.now() + timedelta(days=1)
    data = {
        "lead_id": lead.id,
        "date": future_date.isoformat(),
        "note": "Premier rendez-vous",
    }

    serializer = AppointmentSerializer(
        data=data, context={"request": type("Request", (), {"user": user})()}
    )
    assert serializer.is_valid(), serializer.errors
    instance = serializer.save()
    assert instance.created_by == user
    assert instance.lead == lead
    assert instance.note == "Premier rendez-vous"


def test_invalid_past_date_is_rejected(lead, user):
    """
    Vérifie qu’un rendez-vous dans le passé est refusé.
    """
    past_date = timezone.now() - timedelta(days=1)
    data = {
        "lead_id": lead.id,
        "date": past_date.isoformat(),
    }

    serializer = AppointmentSerializer(
        data=data, context={"request": type("Request", (), {"user": user})()}
    )
    with pytest.raises(ValidationError) as exc_info:
        serializer.is_valid(raise_exception=True)

    assert "date" in exc_info.value.detail
    assert "dans le passé" in str(exc_info.value.detail["date"][0])


def test_read_only_fields_are_present(lead, user):
    """
    Vérifie que les champs read-only sont présents dans la représentation.
    """
    future_date = timezone.now() + timedelta(days=2)
    appointment = Appointment.objects.create(
        lead=lead, date=future_date, note="RDV test", created_by=user
    )

    serializer = AppointmentSerializer(instance=appointment)
    data = serializer.data
    assert data["id"] == appointment.id
    assert data["created_by"] is not None
    assert data["lead"] is not None
    assert "date_display" in data
    assert data["date_display"] == future_date.strftime("%d/%m/%Y %H:%M")
