# tests/test_slot_services.py

from datetime import date, datetime, time, timedelta

import pytest
from django.db import IntegrityError
from django.utils import timezone

from api.booking.models import SlotQuota
from api.booking.services import cancel_booking, list_slots_with_quota, try_book_slot
from api.opening_hours.models import OpeningHours

pytestmark = pytest.mark.django_db


@pytest.fixture
def setup_opening_hours():
    # assuming is_closed is a @property, do not try to assign it
    # override with logic or mock if necessary
    return OpeningHours.objects.create(
        day_of_week=timezone.now().weekday(),
        is_active=True,
        open_time=time(9, 0),
        close_time=time(12, 0),
        slot_duration_minutes=30,
        capacity_per_slot=2,
    )


def test_list_slots_with_quota_creates_slots(setup_opening_hours):
    today = timezone.localdate()
    slots = list_slots_with_quota(today)
    assert len(slots) == 6  # 3h => 6 slots de 30 min
    for slot in slots:
        assert slot["capacity"] == 2
        assert slot["booked"] == 0
        assert slot["remaining"] == 2
        assert not slot["is_full"]


def test_try_book_slot_success(setup_opening_hours):
    today = timezone.localdate()
    slots = list_slots_with_quota(today)
    start_at = slots[0]["start_at"]
    quota = try_book_slot(start_at)
    assert quota.booked == 1
    quota.refresh_from_db()
    assert quota.booked == 1


def test_try_book_slot_over_capacity(setup_opening_hours):
    today = timezone.localdate()
    slots = list_slots_with_quota(today)
    start_at = slots[0]["start_at"]
    try_book_slot(start_at)
    try_book_slot(start_at)
    with pytest.raises(ValueError, match="Créneau complet"):
        try_book_slot(start_at)


def test_cancel_booking_decrements_booked(setup_opening_hours):
    today = timezone.localdate()
    slots = list_slots_with_quota(today)
    start_at = slots[0]["start_at"]
    try_book_slot(start_at)
    cancel_booking(start_at)
    quota = SlotQuota.objects.get(start_at=start_at)
    assert quota.booked == 0


def test_cancel_booking_on_nonexistent_slot():
    dt = timezone.make_aware(datetime.now() + timedelta(days=1))
    # Pas d'erreur si le créneau n'existe pas
    cancel_booking(dt)
    assert SlotQuota.objects.filter(start_at=dt).count() == 0
