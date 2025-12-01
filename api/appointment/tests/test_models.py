# api/appointment/test_models.py
from datetime import timezone as dt_timezone

import pytest
from django.utils import timezone

from api.appointment.models import Appointment
from api.leads.models import Lead
from api.users.models import User, UserRoles

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return User.objects.create_user(
        email="test@example.com",
        password="password",
        role=UserRoles.CONSEILLER,
        first_name="Test",
        last_name="Conseiller",
    )


from api.lead_status.models import LeadStatus


@pytest.fixture
def lead(user):
    # Get a status instance, adjust code as needed
    status, _ = LeadStatus.objects.get_or_create(
        code="NOUVEAU", defaults={"label": "Nouveau"}
    )
    # Create the lead without assigning first
    lead = Lead.objects.create(
        first_name="Alice", last_name="Martin", email="alice@example.com", status=status
    )
    lead.assigned_to.set([user])
    return lead


def test_create_appointment(lead, user):
    """
    Vérifie que l’on peut créer un rendez-vous valide avec les champs requis.
    """
    date = timezone.now() + timezone.timedelta(days=1)
    appointment = Appointment.objects.create(
        lead=lead, date=date, note="Test RDV", created_by=user
    )
    assert appointment.pk is not None
    assert appointment.lead == lead
    assert appointment.created_by == user
    assert appointment.date == date
    assert appointment.note == "Test RDV"


def test_str_method(lead, user):
    """
    Vérifie que la méthode __str__ renvoie une chaîne lisible.
    """
    from datetime import datetime

    date = datetime(2025, 9, 1, 10, 30, tzinfo=dt_timezone.utc)
    appointment = Appointment.objects.create(lead=lead, date=date, created_by=user)
    expected = f"RDV {lead} le 01/09/2025 10:30"
    assert str(appointment) == expected
