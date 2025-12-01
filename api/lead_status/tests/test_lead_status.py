import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from api.lead_status.models import LeadStatus
from api.users.models import User
from api.users.roles import UserRoles


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="admin@example.com",
        password="adminpass",
        first_name="Admin",
        last_name="User",
        role=UserRoles.ADMIN,
    )


@pytest.fixture
def non_admin_user(db):
    return User.objects.create_user(
        email="user@example.com",
        password="userpass",
        first_name="User",
        last_name="Client",
        role=UserRoles.CONSEILLER,
    )


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def lead_status_sample(db):
    return LeadStatus.objects.create(
        code="TEST_STATUS", label="Statut test", color="#00AA00"
    )


@pytest.mark.django_db
class TestLeadStatusAPI:

    def test_list_is_public(self, api_client, lead_status_sample):
        url = reverse("lead-status-list")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        results = response.data.get("results", response.data)
        assert any(s["code"] == "TEST_STATUS" for s in results)

    def test_create_as_admin(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        url = reverse("lead-status-list")
        response = api_client.post(
            url,
            data={"code": "rdv_confirme", "label": "RDV confirmé", "color": "#0000FF"},
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["code"] == "RDV_CONFIRME"

    def test_create_as_non_admin(self, api_client, non_admin_user):
        api_client.force_authenticate(user=non_admin_user)
        url = reverse("lead-status-list")
        response = api_client.post(
            url, data={"code": "non_autorise", "label": "Interdit", "color": "#000"}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_update_as_admin(self, api_client, admin_user, lead_status_sample):
        api_client.force_authenticate(user=admin_user)
        url = reverse("lead-status-detail", args=[lead_status_sample.id])
        response = api_client.patch(url, data={"label": "Modifié"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["label"] == "Modifié"

    def test_update_as_non_admin(self, api_client, non_admin_user, lead_status_sample):
        api_client.force_authenticate(user=non_admin_user)
        url = reverse("lead-status-detail", args=[lead_status_sample.id])
        response = api_client.patch(url, data={"label": "Interdit"})
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_as_admin(self, api_client, admin_user, lead_status_sample):
        api_client.force_authenticate(user=admin_user)
        url = reverse("lead-status-detail", args=[lead_status_sample.id])
        response = api_client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not LeadStatus.objects.filter(id=lead_status_sample.id).exists()

    def test_delete_protected_status(self, api_client, admin_user):
        protected = LeadStatus.objects.create(
            code="RDV_PLANIFIE", label="RDV planifié", color="#999"
        )
        api_client.force_authenticate(user=admin_user)
        url = reverse("lead-status-detail", args=[protected.id])
        response = api_client.delete(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert LeadStatus.objects.filter(id=protected.id).exists()

    def test_delete_as_non_admin(self, api_client, non_admin_user, lead_status_sample):
        api_client.force_authenticate(user=non_admin_user)
        url = reverse("lead-status-detail", args=[lead_status_sample.id])
        response = api_client.delete(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN
