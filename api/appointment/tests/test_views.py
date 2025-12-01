# api/appointment/test_views.py

from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from api.appointment.models import Appointment
from api.leads.models import Lead, LeadStatus
from api.statut_dossier.models import StatutDossier
from api.users.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def admin_user():
    return User.objects.create_user(
        email="admin@example.com",
        password="password",
        role="ADMIN",
        first_name="Admin",
        last_name="User",
    )


@pytest.fixture
def lead():
    from api.leads.models import LeadStatus

    status = LeadStatus.objects.create(code="INCOMPLET", label="Incomplet")
    return Lead.objects.create(
        first_name="Alice", last_name="Martin", email="alice@example.com", status=status
    )


def test_create_appointment_success(client, admin_user, lead):
    with patch("api.utils.email.appointment.tasks.send_appointment_created_task.delay"):
        client.force_authenticate(user=admin_user)
        date = timezone.now() + timezone.timedelta(days=1)
        response = client.post(
            "/api/appointments/",
            {
                "lead_id": lead.id,
                "date": date.isoformat(),
                "note": "Premier rendez-vous",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert Appointment.objects.count() == 1
        appointment = Appointment.objects.first()
        assert appointment.lead == lead
        assert appointment.created_by == admin_user


def test_create_appointment_in_past_fails(client, admin_user, lead):
    client.force_authenticate(user=admin_user)
    past_date = timezone.now() - timezone.timedelta(days=1)
    response = client.post(
        "/api/appointments/",
        {
            "lead_id": lead.id,
            "date": past_date.isoformat(),
            "note": "RDV dans le passé",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "La date du rendez-vous ne peut pas être dans le passé" in str(response.data)


def test_list_appointments(client, admin_user, lead):
    client.force_authenticate(user=admin_user)
    future_date = timezone.now() + timezone.timedelta(days=2)
    Appointment.objects.create(
        lead=lead, date=future_date, note="Rendez-vous de test", created_by=admin_user
    )
    response = client.get("/api/appointments/")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) >= 1
    assert any(
        item.get("note") == "Rendez-vous de test"
        for item in response.data.get("results", response.data)
    )


def test_delete_appointment(client, admin_user, lead):
    with patch("api.appointment.views.send_appointment_deleted_task.delay"):
        client.force_authenticate(user=admin_user)
        appointment = Appointment.objects.create(
            lead=lead,
            date=timezone.now() + timezone.timedelta(days=1),
            note="À supprimer",
            created_by=admin_user,
        )
        response = client.delete(f"/api/appointments/{appointment.id}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert Appointment.objects.count() == 0
