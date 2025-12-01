# tests/test_models.py (ou api/booking/tests/test_models.py)

from datetime import datetime, time, timedelta

import pytest
from django.utils import timezone

from api.booking.models import SlotQuota

pytestmark = pytest.mark.django_db


def test_slot_quota_remaining():
    quota = SlotQuota(start_at=timezone.now(), capacity=5, booked=3)
    assert quota.remaining == 2

    quota.booked = 5
    assert quota.remaining == 0

    quota.booked = 7
    assert quota.remaining == 0  # jamais < 0


def test_slot_quota_str():
    dt = timezone.now().replace(microsecond=0)
    quota = SlotQuota(start_at=dt, capacity=3, booked=1)
    assert str(quota) == f"{dt} — 1/3"
