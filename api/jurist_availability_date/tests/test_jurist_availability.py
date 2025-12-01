from datetime import time

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from api.jurist_availability_date.models import JuristGlobalAvailability

pytestmark = pytest.mark.django_db


# ----------------------
# TEST MODEL
# ----------------------
def test_jurist_global_availability_str():
    obj = JuristGlobalAvailability.objects.create(
        day_of_week=1, start_time=time(10, 0), end_time=time(12, 0)  # Mardi
    )
    assert str(obj) == "Mardi de 10:00 à 12:00"


# ----------------------
# TEST SERIALIZER
# ----------------------
from api.jurist_availability_date.serializers import JuristGlobalAvailabilitySerializer


def test_jurist_global_availability_serializer():
    obj = JuristGlobalAvailability.objects.create(
        day_of_week=4, start_time=time(9, 30), end_time=time(11, 0)  # Vendredi
    )
    serializer = JuristGlobalAvailabilitySerializer(obj)
    expected = {
        "id": obj.id,
        "day_of_week": 4,
        "day_of_week_display": "Vendredi",
        "start_time": "09:30:00",
        "end_time": "11:00:00",
    }
    assert serializer.data == expected


# ----------------------
# TEST VIEWSET (API)
# ----------------------
@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def availability():
    return JuristGlobalAvailability.objects.create(
        day_of_week=3, start_time=time(14, 0), end_time=time(16, 0)  # Jeudi
    )


def test_list_jurist_global_availability(client, availability):
    response = client.get("/api/jurist-global-availability/")
    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["results"][0]["day_of_week"] == 3
    assert response.data["results"][0]["day_of_week_display"] == "Jeudi"


def test_retrieve_jurist_global_availability(client, availability):
    response = client.get(f"/api/jurist-global-availability/{availability.id}/")
    assert response.status_code == 200
    assert response.data["day_of_week"] == 3


def test_days_endpoint(auth_client):
    JuristGlobalAvailability.objects.create(
        day_of_week=1, start_time=time(10), end_time=time(11)
    )
    JuristGlobalAvailability.objects.create(
        day_of_week=3, start_time=time(14), end_time=time(15)
    )
    response = auth_client.get("/api/jurist-global-availability/days/")
    assert response.status_code == 200
    assert response.data == [1, 3]


# ----------------------
# TEST PERMISSIONS
# ----------------------
from api.users.models import User, UserRoles


@pytest.fixture
def admin_user():
    return User.objects.create_user(
        email="admin@test.com",
        password="adminpass",
        role=UserRoles.ADMIN,
        first_name="Admin",
        last_name="User",
    )


@pytest.fixture
def auth_client(client, admin_user):
    client.force_authenticate(user=admin_user)
    return client


def test_create_jurist_global_availability_as_admin(auth_client):
    data = {"day_of_week": 2, "start_time": "10:00", "end_time": "12:00"}
    response = auth_client.post("/api/jurist-global-availability/", data)
    assert response.status_code == status.HTTP_201_CREATED
    assert JuristGlobalAvailability.objects.count() == 1


def test_create_jurist_global_availability_forbidden_as_anonymous(client):
    data = {"day_of_week": 2, "start_time": "10:00", "end_time": "12:00"}
    response = client.post("/api/jurist-global-availability/", data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
