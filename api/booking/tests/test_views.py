from datetime import time, timedelta

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from api.booking.models import SlotQuota
from api.leads.constants import RDV_PLANIFIE
from api.leads.models import Lead, LeadStatus
from api.opening_hours.models import OpeningHours

pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def lead_status_rdv_planifie():
    return LeadStatus.objects.create(code=RDV_PLANIFIE, label="RDV Planifié")


@pytest.fixture
def opening_hours_mardi():
    return OpeningHours.objects.create(
        day_of_week=1,  # mardi
        # is_closed is a @property, no setter — remove or avoid setting
        is_active=True,
        open_time=time(10, 0),
        close_time=time(12, 0),
        slot_duration_minutes=30,
        capacity_per_slot=2,
    )


def test_slots_for_date_returns_slots(client, opening_hours_mardi):
    date = timezone.now().date()
    # S'assurer que la date est bien un mardi
    while date.weekday() != 1:
        date += timedelta(days=1)

    response = client.get(f"/api/booking/slots/?date={date.isoformat()}")

    assert response.status_code == 200
    slots = response.json()
    assert isinstance(slots, list)
    assert len(slots) == 4  # 10:00, 10:30, 11:00, 11:30
    assert all("start_at" in slot for slot in slots)
    assert all("capacity" in slot for slot in slots)


def test_slots_for_date_requires_valid_date(client):
    response = client.get("/api/booking/slots/?date=invalid-date")
    assert response.status_code == 400
    assert "date" in response.data["detail"].lower()


def test_public_book_fails_on_full_slot(
    client, lead_status_rdv_planifie, opening_hours_mardi
):
    # on force un créneau plein
    date = timezone.now().date()
    while date.weekday() != 1:
        date += timedelta(days=1)

    from api.booking.services import try_book_slot

    slot_time = timezone.make_aware(timezone.datetime.combine(date, time(10, 0)))
    try_book_slot(slot_time)
    try_book_slot(slot_time)  # 2/2 → plein

    data = {
        "first_name": "Bob",
        "last_name": "Dupont",
        "phone": "+33600000000",
        "date": date.isoformat(),
        "time": "10:00",
    }

    response = client.post("/api/booking/book/", data=data, format="json")
    assert response.status_code == 409
    assert "complet" in response.data["detail"].lower()


def test_public_book_invalid_date_format(client):
    data = {
        "first_name": "Alice",
        "last_name": "Martin",
        "date": "2025-99-99",
        "time": "25:00",
    }
    response = client.post("/api/booking/book/", data=data, format="json")
    assert response.status_code == 400
    assert "format" in response.data["detail"].lower()
