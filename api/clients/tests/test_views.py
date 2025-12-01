import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from api.clients.models import Client
from api.lead_status.models import LeadStatus  # ou StatutDossier si renommé
from api.leads.models import Lead

# Active la base de données pour tous les tests
pytestmark = pytest.mark.django_db


# 🔹 Client API pour les requêtes
@pytest.fixture
def api_client():
    return APIClient()


# 🔹 Utilisateur authentifié (CustomUser sans username)
@pytest.fixture
def user():
    return get_user_model().objects.create_user(
        email="test@example.com",
        first_name="Test",
        last_name="User",
        password="testpass",
    )


# 🔹 Statut par défaut requis par le Lead
@pytest.fixture
def default_status():
    return LeadStatus.objects.create(code="NOUVEAU", label="Nouveau", color="#0000FF")


# 🔹 Lead valide avec statut obligatoire
@pytest.fixture
def lead(default_status):
    return Lead.objects.create(
        first_name="John",
        last_name="Doe",
        email="john@example.com",
        phone="+33123456789",
        status=default_status,
    )


# 🔹 Données minimales valides pour créer un client
@pytest.fixture
def valid_client_data():
    return {
        "civilite": "MONSIEUR",
        "date_naissance": "1990-01-01",
        "lieu_naissance": "Paris",
        "pays": "France",
        "nationalite": "Française",
    }


# 🔸 Test POST anonyme autorisé
def test_create_client_anonymous_allowed(api_client, lead, valid_client_data):
    url = reverse("client-list") + f"?id={lead.id}"
    response = api_client.post(url, data=valid_client_data, format="json")
    assert response.status_code == 201, response.data
    assert Client.objects.count() == 1
    assert Client.objects.first().lead == lead


# 🔸 Test POST authentifié autorisé
def test_create_client_authenticated_allowed(api_client, user, lead, valid_client_data):
    api_client.force_authenticate(user=user)
    url = reverse("client-list") + f"?id={lead.id}"
    response = api_client.post(url, data=valid_client_data, format="json")
    assert response.status_code == 201, response.data
    assert Client.objects.count() == 1
    assert Client.objects.first().lead == lead


# 🔸 Test GET anonyme refusé
def test_list_clients_anonymous_forbidden(api_client):
    url = reverse("client-list")
    response = api_client.get(url)
    assert response.status_code in [401, 403]  # selon la config DRF


# 🔸 Test GET authentifié autorisé
def test_list_clients_authenticated_allowed(api_client, user):
    api_client.force_authenticate(user=user)
    url = reverse("client-list")
    response = api_client.get(url)
    assert response.status_code == 200
