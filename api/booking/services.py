from datetime import date as date_cls
from datetime import datetime, time, timedelta

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from api.booking.models import SlotQuota
from api.opening_hours.models import OpeningHours


def get_rules_for_date(d: date_cls):
    """
    Retourne (open_time, close_time, slot_minutes, capacity) pour la date 'd'
    en se basant uniquement sur OpeningHours (hebdo).
    """
    weekday = d.weekday()  # 0 = lundi ... 6 = dimanche
    oh = OpeningHours.objects.filter(day_of_week=weekday, is_active=True).first()
    if not oh or oh.is_closed:
        return None
    return (oh.open_time, oh.close_time, oh.slot_duration_minutes, oh.capacity_per_slot)


def iter_slots(d: date_cls, open_t: time, close_t: time, step_min: int):
    """
    Génère les datetime aware (TZ courante) pour chaque début de créneau entre
    open_t (inclus) et close_t (exclus).
    """
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(d, open_t), tz)
    end = timezone.make_aware(datetime.combine(d, close_t), tz)
    cur = start
    delta = timedelta(minutes=step_min)
    while cur < end:
        yield cur
        cur += delta


def list_slots_with_quota(d: date_cls):
    """
    Liste des créneaux pour la date 'd' avec (capacity/booked/remaining/is_full).
    Crée le SlotQuota si absent (avec la capacity courante).
    """
    rules = get_rules_for_date(d)
    if not rules:
        return []

    open_t, close_t, step, capacity = rules
    out = []
    for start_at in iter_slots(d, open_t, close_t, step):
        quota, _ = SlotQuota.objects.get_or_create(
            start_at=start_at, defaults={"capacity": capacity, "booked": 0}
        )
        # réalignement de capacité si les règles ont changé
        if quota.capacity != capacity:
            SlotQuota.objects.filter(pk=quota.pk).update(capacity=capacity)
            quota.capacity = capacity

        out.append(
            {
                "start_at": start_at,
                "time": start_at.strftime("%H:%M"),
                "capacity": quota.capacity,
                "booked": quota.booked,
                "remaining": quota.remaining,
                "is_full": quota.booked >= quota.capacity,
            }
        )
    return out


@transaction.atomic
def try_book_slot(start_at: datetime):
    """
    Réserve atomiquement un créneau (incrémente booked si capacité disponible).
    Lève ValueError si plein ou si jour non ouvert.
    """
    d = start_at.date()
    rules = get_rules_for_date(d)
    if not rules:
        raise ValueError("Aucun horaire d’ouverture pour cette date")

    _, _, _, capacity = rules

    # verrou pessimiste sur la ligne
    quota, _ = SlotQuota.objects.select_for_update().get_or_create(
        start_at=start_at, defaults={"capacity": capacity, "booked": 0}
    )
    # réalignement capacité
    if quota.capacity != capacity:
        quota.capacity = capacity
        quota.save(update_fields=["capacity"])

    if quota.booked >= quota.capacity:
        raise ValueError("Créneau complet")

    SlotQuota.objects.filter(pk=quota.pk).update(booked=F("booked") + 1)
    quota.booked += 1
    return quota


@transaction.atomic
def cancel_booking(start_at: datetime):
    """
    Annule une réservation (décrémente booked si > 0).
    À appeler si un RDV est annulé/déplacé.
    """
    try:
        quota = SlotQuota.objects.select_for_update().get(start_at=start_at)
    except SlotQuota.DoesNotExist:
        return
    if quota.booked > 0:
        SlotQuota.objects.filter(pk=quota.pk).update(booked=F("booked") - 1)
