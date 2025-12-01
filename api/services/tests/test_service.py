from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from api.services.models import Service
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
def conseiller_user(db):
    return User.objects.create_user(
        email="user@example.com",
        password="userpass",
        first_name="User",
        last_name="Conseiller",
        role=UserRoles.CONSEILLER,
    )


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def service_sample(db):
    return Service.objects.create(
        code="TITRE_SEJOUR", label="Titre de séjour", price=Decimal("120.00")
    )


@pytest.mark.django_db
class TestServiceViewSet:

    def test_create_service_as_admin(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        url = reverse("services-list")
        response = api_client.post(
            url,
            data={
                "code": "titre sejour",
                "label": "Titre de Séjour",
                "price": "150.00",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["code"] == "TITRESEJOUR"
        assert response.data["label"] == "Titre de Séjour"

    def test_create_service_as_non_admin(self, api_client, conseiller_user):
        api_client.force_authenticate(user=conseiller_user)
        url = reverse("services-list")
        response = api_client.post(
            url,
            data={
                "code": "naturalisation",
                "label": "Naturalisation",
                "price": "180.00",
            },
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_update_service_as_admin(self, api_client, admin_user, service_sample):
        api_client.force_authenticate(user=admin_user)
        url = reverse("services-detail", args=[service_sample.id])
        response = api_client.patch(url, data={"price": "130.00"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["price"] == "130.00"

    def test_update_service_as_non_admin(
        self, api_client, conseiller_user, service_sample
    ):
        api_client.force_authenticate(user=conseiller_user)
        url = reverse("services-detail", args=[service_sample.id])
        response = api_client.patch(url, data={"price": "50.00"})
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_service_as_admin(self, api_client, admin_user, service_sample):
        api_client.force_authenticate(user=admin_user)
        url = reverse("services-detail", args=[service_sample.id])
        response = api_client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Service.objects.filter(id=service_sample.id).exists()

    def test_delete_service_as_non_admin(
        self, api_client, conseiller_user, service_sample
    ):
        api_client.force_authenticate(user=conseiller_user)
        url = reverse("services-detail", args=[service_sample.id])
        response = api_client.delete(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN
