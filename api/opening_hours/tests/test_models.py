from datetime import time

import pytest

from api.opening_hours.models import OpeningHours

pytestmark = pytest.mark.django_db


def test_opening_hours_is_closed_returns_false_when_open_and_active():
    oh = OpeningHours.objects.create(
        day_of_week=1,  # Mardi
        open_time=time(9, 0),
        close_time=time(17, 0),
        slot_duration_minutes=30,
        capacity_per_slot=2,
        is_active=True,
    )
    assert oh.is_closed is False


def test_opening_hours_is_closed_returns_true_when_inactive():
    oh = OpeningHours.objects.create(
        day_of_week=2, open_time=time(9, 0), close_time=time(17, 0), is_active=False
    )
    assert oh.is_closed is True


def test_opening_hours_is_closed_returns_true_when_missing_hours():
    oh = OpeningHours.objects.create(
        day_of_week=3, open_time=None, close_time=None, is_active=True
    )
    assert oh.is_closed is True


def test_opening_hours_str_when_closed():
    oh = OpeningHours.objects.create(day_of_week=6, is_active=False)  # Dimanche
    assert str(oh) == "Dimanche: Fermé"


def test_opening_hours_str_when_open():
    oh = OpeningHours.objects.create(
        day_of_week=0,
        open_time=time(8, 30),
        close_time=time(12, 30),
        slot_duration_minutes=45,
        capacity_per_slot=3,
        is_active=True,
    )
    assert str(oh) == "Lundi: 08:30 - 12:30 (45 min, cap 3)"
