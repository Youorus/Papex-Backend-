import datetime

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from api.user_unavailability.models import UserUnavailability
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
        email="conseiller@example.com",
        password="userpass",
        first_name="Conseiller",
        last_name="User",
        role=UserRoles.CONSEILLER,
    )


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def unavailability_sample(db, conseiller_user):
    return UserUnavailability.objects.create(
        user=conseiller_user,
        start_date=datetime.date.today(),
        end_date=datetime.date.today() + datetime.timedelta(days=2),
        label="Congés",
    )


@pytest.mark.django_db
class TestUserUnavailabilityViewSet:

    def test_list_unavailability_public(self, api_client, unavailability_sample):
        url = reverse("user-unavailability-list")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        results = (
            data["results"] if isinstance(data, dict) and "results" in data else data
        )
        assert any(u["label"] == "Congés" for u in results)

    def test_retrieve_unavailability_public(self, api_client, unavailability_sample):
        url = reverse("user-unavailability-detail", args=[unavailability_sample.id])
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["label"] == "Congés"

    def test_create_unavailability_as_admin(
        self, api_client, admin_user, conseiller_user
    ):
        api_client.force_authenticate(user=admin_user)
        url = reverse("user-unavailability-list")
        response = api_client.post(
            url,
            data={
                "user": str(conseiller_user.id),
                "start_date": "2025-09-01",
                "end_date": "2025-09-05",
                "label": "Mission",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["label"] == "Mission"

    def test_update_unavailability_as_admin(
        self, api_client, admin_user, unavailability_sample
    ):
        api_client.force_authenticate(user=admin_user)
        url = reverse("user-unavailability-detail", args=[unavailability_sample.id])
        response = api_client.patch(url, data={"label": "Formation"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["label"] == "Formation"

    def test_delete_unavailability_as_admin(
        self, api_client, admin_user, unavailability_sample
    ):
        api_client.force_authenticate(user=admin_user)
        url = reverse("user-unavailability-detail", args=[unavailability_sample.id])
        response = api_client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not UserUnavailability.objects.filter(
            id=unavailability_sample.id
        ).exists()
