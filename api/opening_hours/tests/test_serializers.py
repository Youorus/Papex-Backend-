from datetime import time

import pytest

from api.opening_hours.serializers import OpeningHoursSerializer

pytestmark = pytest.mark.django_db


def test_valid_opening_hours_serializer_full_data():
    data = {
        "day_of_week": 2,
        "open_time": "09:00",
        "close_time": "17:00",
        "slot_duration_minutes": 30,
        "capacity_per_slot": 2,
        "is_active": True,
    }
    serializer = OpeningHoursSerializer(data=data)
    assert serializer.is_valid(), serializer.errors
    instance = serializer.save()
    assert instance.day_of_week == 2
    assert instance.open_time == time(9, 0)


def test_invalid_when_active_and_times_missing():
    data = {
        "day_of_week": 3,
        "is_active": True,
        "open_time": None,
        "close_time": None,
    }
    serializer = OpeningHoursSerializer(data=data)
    assert not serializer.is_valid()
    assert "open_time" in serializer.errors
    assert "close_time" in serializer.errors


def test_invalid_when_open_greater_than_close():
    data = {
        "day_of_week": 4,
        "open_time": "18:00",
        "close_time": "09:00",
        "is_active": True,
    }
    serializer = OpeningHoursSerializer(data=data)
    assert not serializer.is_valid()
    assert "close_time" in serializer.errors


def test_valid_when_inactive_and_hours_missing():
    data = {
        "day_of_week": 5,
        "is_active": False,
        "open_time": None,
        "close_time": None,
    }
    serializer = OpeningHoursSerializer(data=data)
    assert serializer.is_valid(), serializer.errors


def test_invalid_when_only_one_hour_provided_and_active():
    data = {
        "day_of_week": 6,
        "open_time": "10:00",
        "close_time": None,
        "is_active": True,
    }
    serializer = OpeningHoursSerializer(data=data)
    assert not serializer.is_valid()
    assert "open_time" in serializer.errors
    assert "close_time" in serializer.errors
