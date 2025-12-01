import pytest

"""
Tests d’intégration pour les vues de l’API Lead.

Ces tests couvrent :
- la création, récupération, modification et suppression d’un lead,
- les filtres par statut, recherche et date,
- l’assignation à des conseillers ou juristes,
- les envois d’e-mails (formulaire, rendez-vous) simulés via des mocks.

Tous les tests nécessitent un accès à la base de données (pytestmark).
"""
from unittest.mock import patch

from django.urls import reverse
from rest_framework.test import APIClient

from api.lead_status.models import LeadStatus
from api.leads.constants import RDV_PLANIFIE
from api.leads.models import Lead
from api.users.models import User
from api.users.roles import UserRoles

pytestmark = pytest.mark.django_db


@pytest.fixture
def lead_status():
    return LeadStatus.objects.create(code=RDV_PLANIFIE, label="Planifié")


@pytest.fixture
def admin_user():
    return User.objects.create_user(
        email="admin@test.com",
        password="123",
        role=UserRoles.ADMIN,
        first_name="Admin",
        last_name="User",
    )


@pytest.fixture
def conseiller_user():
    return User.objects.create_user(
        email="conseiller@test.com",
        password="123",
        role=UserRoles.CONSEILLER,
        first_name="Conseiller",
        last_name="User",
    )


@pytest.fixture
def juriste_user():
    return User.objects.create_user(
        email="juriste@test.com",
        password="123",
        role=UserRoles.JURISTE,
        first_name="Juriste",
        last_name="User",
    )


@pytest.fixture
def client_for():
    def _client(user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    return _client


@patch("api.utils.email.leads.tasks.send_appointment_planned_task.delay")
def test_create_lead_success(mock_notify, client_for, admin_user, lead_status):
    client = client_for(admin_user)
    url = reverse("lead-list")
    payload = {
        "first_name": "Sarah",
        "last_name": "Martin",
        "phone": "+33600000000",
        "email": "sarah@example.com",
        "status_id": lead_status.id,
        "appointment_date": "01/09/2025 10:00",
    }
    response = client.post(url, data=payload, format="json")
    assert response.status_code == 201, response.data
    assert Lead.objects.count() == 1
    mock_notify.assert_called_once()


def test_retrieve_lead(client_for, admin_user, lead_status):
    lead = Lead.objects.create(
        first_name="X", last_name="Y", phone="+336", status=lead_status
    )
    client = client_for(admin_user)
    url = reverse("lead-detail", kwargs={"pk": lead.pk})
    response = client.get(url)
    assert response.status_code == 200
    assert response.data["first_name"] == "X"


def test_filter_leads_by_status(client_for, admin_user, lead_status):
    lead1 = Lead.objects.create(
        first_name="A", last_name="X", phone="+1", status=lead_status
    )
    lead2 = Lead.objects.create(
        first_name="B", last_name="Y", phone="+2", status=lead_status
    )

    client = client_for(admin_user)
    url = reverse("lead-list") + f"?status={lead_status.id}"
    response = client.get(url)

    assert response.status_code == 200
    assert lead1.id in [
        item["id"] for item in response.data.get("results", response.data)
    ]
    assert lead2.id in [
        item["id"] for item in response.data.get("results", response.data)
    ]


def test_filter_leads_by_search(client_for, admin_user, lead_status):
    Lead.objects.create(
        first_name="Jean",
        last_name="Doe",
        phone="+331",
        email="jean@example.com",
        status=lead_status,
    )
    Lead.objects.create(
        first_name="Marie",
        last_name="Curie",
        phone="+332",
        email="marie@example.com",
        status=lead_status,
    )

    client = client_for(admin_user)
    url = reverse("lead-list") + "?search=jean"
    response = client.get(url)
    assert response.status_code == 200
    emails = [
        item["email"].lower() for item in response.data.get("results", response.data)
    ]
    assert any("jean" in email for email in emails)


def test_filter_leads_by_date(client_for, admin_user, lead_status):
    lead = Lead.objects.create(
        first_name="Alice", last_name="X", phone="+33", status=lead_status
    )
    date_str = lead.created_at.strftime("%Y-%m-%d")

    client = client_for(admin_user)
    url = reverse("lead-list") + f"?date={date_str}&date_field=created_at"
    response = client.get(url)
    assert response.status_code == 200
    results = response.data.get("results", response.data)
    assert lead.id in [item["id"] for item in results]


def test_patch_lead_phone(client_for, admin_user, lead_status):
    lead = Lead.objects.create(
        first_name="Jean",
        last_name="Doe",
        phone="+33611112222",
        status=lead_status,
        appointment_date="2025-09-01T10:00:00Z",
    )
    client = client_for(admin_user)
    url = reverse("lead-detail", kwargs={"pk": lead.pk})
    response = client.patch(url, data={"phone": "+33777777777"}, format="json")
    assert response.status_code == 200, response.data
    lead.refresh_from_db()
    assert lead.phone == "+33777777777"


def test_admin_can_delete_lead(client_for, admin_user, lead_status):
    lead = Lead.objects.create(
        first_name="Delete", last_name="Me", phone="+336", status=lead_status
    )
    client = client_for(admin_user)
    url = reverse("lead-detail", kwargs={"pk": lead.pk})
    response = client.delete(url)
    assert response.status_code == 204
    assert not Lead.objects.filter(pk=lead.pk).exists()


def test_count_by_status(client_for, admin_user, lead_status):
    Lead.objects.create(
        first_name="Count", last_name="Me", phone="+336", status=lead_status
    )
    client = client_for(admin_user)
    url = reverse("lead-count-by-status")
    response = client.get(url)
    assert response.status_code == 200
    assert RDV_PLANIFIE in response.data


def test_assignment_admin(client_for, admin_user, conseiller_user, lead_status):
    lead = Lead.objects.create(
        first_name="Assign", last_name="Me", phone="+336", status=lead_status
    )
    client = client_for(admin_user)
    url = reverse("lead-assignment", kwargs={"pk": lead.pk})
    response = client.patch(url, {"assign": [conseiller_user.id]}, format="json")
    assert response.status_code == 200
    lead.refresh_from_db()
    assert conseiller_user in lead.assigned_to.all()


def test_assign_juriste_admin(client_for, admin_user, juriste_user, lead_status):
    lead = Lead.objects.create(
        first_name="J", last_name="R", phone="+336", status=lead_status
    )
    client = client_for(admin_user)
    url = reverse("lead-assign-juristes", kwargs={"pk": lead.pk})
    response = client.patch(url, {"assign": [juriste_user.id]}, format="json")
    assert response.status_code == 200
    lead.refresh_from_db()
    assert juriste_user in lead.jurist_assigned.all()


@patch("api.utils.email.leads.tasks.send_formulaire_task.delay")
def test_send_formulaire_email(mock_task, client_for, admin_user, lead_status):
    lead = Lead.objects.create(
        first_name="Form",
        last_name="Email",
        phone="+336",
        email="test@test.com",
        status=lead_status,
        appointment_date="2025-09-01T10:00:00Z",
    )
    client = client_for(admin_user)
    url = reverse("lead-send-formulaire-email", kwargs={"pk": lead.pk})
    response = client.post(url)
    assert response.status_code == 200
    mock_task.assert_called_once_with(lead.pk)
