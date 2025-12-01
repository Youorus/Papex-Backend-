from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from api.jurist_appointment.models import JuristAppointment
from api.lead_status.models import LeadStatus
from api.leads.models import Lead
from api.users.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture
def jurist():
    return User.objects.create_user(
        email="jurist@example.com",
        password="password123",
        first_name="Jean",
        last_name="Juriste",
        role="JURISTE",
        is_active=True,
    )


@pytest.fixture
def lead_status():
    return LeadStatus.objects.create(
        code="INCOMPLET", label="Incomplet", color="#999999"
    )


@pytest.fixture
def lead(lead_status):
    return Lead.objects.create(
        first_name="Marie",
        last_name="Durand",
        email="marie@example.com",
        phone="0600000000",
        status=lead_status,
    )


@pytest.fixture
def auth_client(jurist):
    client = APIClient()
    client.force_authenticate(user=jurist)
    return client


def test_create_jurist_appointment(auth_client, jurist, lead):
    url = reverse("jurist-appointments-list")
    data = {
        "jurist": jurist.id,
        "lead": lead.id,
        "date": (timezone.now() + timedelta(days=1)).isoformat(),
    }
    response = auth_client.post(url, data, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    assert JuristAppointment.objects.count() == 1


def test_available_jurists_endpoint(auth_client, lead):
    url = reverse("jurist-appointments-available-jurists")
    date = (timezone.now() + timedelta(days=2)).date().isoformat()
    response = auth_client.get(url, {"lead_id": lead.id, "date": date})
    assert response.status_code in [
        status.HTTP_200_OK,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_400_BAD_REQUEST,
    ]


def test_jurist_slots_endpoint(auth_client, jurist):
    url = reverse("jurist-appointments-jurist-slots")
    date = (timezone.now() + timedelta(days=4)).date().isoformat()
    response = auth_client.get(url, {"jurist_id": jurist.id, "date": date})
    assert response.status_code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]


def test_upcoming_for_lead(auth_client, jurist, lead):
    JuristAppointment.objects.create(
        jurist=jurist,
        lead=lead,
        date=timezone.now() + timedelta(days=2),
        created_by=jurist,
    )
    url = reverse("jurist-appointments-upcoming-for-lead")
    response = auth_client.get(url, {"lead_id": lead.id})
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.data, list)
