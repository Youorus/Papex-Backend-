import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from api.users.models import User
from api.users.roles import UserRoles

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_user():
    return User.objects.create_user(
        email="admin@example.com",
        password="adminpass",
        first_name="Admin",
        last_name="User",
        role=UserRoles.ADMIN,
    )


@pytest.fixture
def api_client(admin_user):
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client


def test_list_users(api_client, admin_user):
    url = reverse("users-list")
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert any(user["email"] == admin_user.email for user in response.data)


def test_change_password(api_client, admin_user):
    url = reverse("users-change-password", kwargs={"pk": admin_user.id})
    response = api_client.patch(url, {"new_password": "new_secure_password"})
    assert response.status_code == status.HTTP_200_OK

    # Vérifie que le mot de passe a bien été modifié
    admin_user.refresh_from_db()
    assert admin_user.check_password("new_secure_password")


def test_list_juristes(api_client):
    url = reverse("users-juristes")
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.data, list)


def test_list_conseillers(api_client):
    url = reverse("users-conseillers")
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.data, list)
