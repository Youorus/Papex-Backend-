from datetime import date

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from api.special_closing_period.models import SpecialClosingPeriod
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
        is_staff=True,  # important pour IsAdminUser
    )


@pytest.fixture
def conseiller_user(db):
    return User.objects.create_user(
        email="user@example.com",
        password="userpass",
        first_name="User",
        last_name="Conseiller",
        role=UserRoles.CONSEILLER,
        is_staff=False,
    )


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def closing_period_sample(db):
    return SpecialClosingPeriod.objects.create(
        label="Noël", start_date=date(2025, 12, 24), end_date=date(2025, 12, 26)
    )


@pytest.mark.django_db
class TestSpecialClosingPeriodViewSet:

    def test_list_is_public(self, api_client, closing_period_sample):
        url = reverse("special-closing-periods-list")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert any(p["label"] == "Noël" for p in response.json().get("results", []))

    def test_create_as_admin(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        url = reverse("special-closing-periods-list")
        response = api_client.post(
            url,
            data={
                "label": "Fête nationale",
                "start_date": "2025-07-14",
                "end_date": "2025-07-14",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["label"] == "Fête nationale"

    def test_update_as_admin(self, api_client, admin_user, closing_period_sample):
        api_client.force_authenticate(user=admin_user)
        url = reverse("special-closing-periods-detail", args=[closing_period_sample.id])
        response = api_client.patch(url, data={"label": "Noël modifié"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["label"] == "Noël modifié"

    def test_delete_as_admin(self, api_client, admin_user, closing_period_sample):
        api_client.force_authenticate(user=admin_user)
        url = reverse("special-closing-periods-detail", args=[closing_period_sample.id])
        response = api_client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not SpecialClosingPeriod.objects.filter(
            id=closing_period_sample.id
        ).exists()
