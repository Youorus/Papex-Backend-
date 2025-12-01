from datetime import time

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from api.opening_hours.models import OpeningHours
from api.users.models import User
from api.users.roles import UserRoles

pytestmark = pytest.mark.django_db


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
def regular_user():
    return User.objects.create_user(
        email="user@test.com",
        password="123",
        role=UserRoles.CONSEILLER,
        first_name="User",
        last_name="Test",
    )


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def opening_hour():
    return OpeningHours.objects.create(
        day_of_week=1,
        open_time=time(9, 0),
        close_time=time(12, 0),
        slot_duration_minutes=30,
        capacity_per_slot=2,
        is_active=True,
    )


def test_list_opening_hours(client, opening_hour):
    response = client.get("/api/opening-hours/")
    assert response.status_code == 200
    assert isinstance(
        response.data, dict
    ), f"Expected dict, got {type(response.data)}: {response.data}"
    assert (
        "results" in response.data
    ), f"'results' key not in response data: {response.data}"
    results = response.data["results"]
    assert isinstance(
        results, list
    ), f"Expected 'results' to be list, got {type(results)}: {results}"
    for item in results:
        assert isinstance(item, dict), f"Expected dict, got {type(item)}: {item}"
    assert any(item.get("day_of_week") == 1 for item in results)


def test_retrieve_opening_hour(client, opening_hour):
    response = client.get(f"/api/opening-hours/{opening_hour.id}/")
    assert response.status_code == 200
    assert response.data["day_of_week"] == 1


def test_create_opening_hour_as_admin(client, admin_user):
    client.force_authenticate(user=admin_user)
    data = {
        "day_of_week": 2,
        "open_time": "08:00",
        "close_time": "12:00",
        "slot_duration_minutes": 30,
        "capacity_per_slot": 3,
        "is_active": True,
    }
    response = client.post("/api/opening-hours/", data=data)
    assert response.status_code == 201
    assert OpeningHours.objects.filter(day_of_week=2).exists()


def test_create_opening_hour_as_regular_user(client, regular_user):
    client.force_authenticate(user=regular_user)
    data = {
        "day_of_week": 3,
        "open_time": "08:00",
        "close_time": "12:00",
        "slot_duration_minutes": 30,
        "capacity_per_slot": 3,
        "is_active": True,
    }
    response = client.post("/api/opening-hours/", data=data)
    assert (
        response.status_code == 403
    ), f"Expected 403 but got {response.status_code} with data: {response.data}"


def test_update_opening_hour_as_admin(client, admin_user, opening_hour):
    client.force_authenticate(user=admin_user)
    response = client.patch(
        f"/api/opening-hours/{opening_hour.id}/", {"capacity_per_slot": 5}
    )
    assert response.status_code == 200
    opening_hour.refresh_from_db()
    assert opening_hour.capacity_per_slot == 5


def test_delete_opening_hour_as_admin(client, admin_user, opening_hour):
    client.force_authenticate(user=admin_user)
    response = client.delete(f"/api/opening-hours/{opening_hour.id}/")
    assert response.status_code == 204
    assert not OpeningHours.objects.filter(id=opening_hour.id).exists()


def test_delete_opening_hour_as_regular_user(client, regular_user, opening_hour):
    client.force_authenticate(user=regular_user)
    response = client.delete(f"/api/opening-hours/{opening_hour.id}/")
    assert (
        response.status_code == 403
    ), f"Expected 403 but got {response.status_code} with data: {response.data}"
