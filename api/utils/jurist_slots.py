from datetime import datetime, timedelta
from django.db.models import Q
from django.utils.timezone import get_current_timezone, make_aware

from api.jurist_availability_date.models import JuristGlobalAvailability
from api.jurist_appointment.models import JuristAppointment

SLOT_DURATION = timedelta(minutes=30)


def is_valid_day(day, jurist=None):
    """
    ✅ CORRECTION MAJEURE : Les disponibilités globales rendent TOUS les juristes disponibles

    Retourne True si au moins une plage de disponibilité existe ce jour-là.
    - Les disponibilités globales s'appliquent à TOUS les juristes
    - Les disponibilités spécifiques s'appliquent uniquement au juriste assigné
    """
    # Django week_day: 1=dimanche, 2=lundi, ..., 7=samedi
    # Python weekday(): 0=lundi, 1=mardi, ..., 6=dimanche
    # Conversion: weekday() + 2, avec wrapping pour dimanche
    django_weekday = (day.weekday() + 2) % 7
    if django_weekday == 0:
        django_weekday = 7

    # Vérifier les disponibilités globales (valides pour TOUS les juristes)
    global_availabilities = JuristGlobalAvailability.objects.filter(
        Q(date=day) | Q(repeat_weekly=True, date__week_day=django_weekday),
        availability_type='global',
        is_active=True
    ).exists()

    # ✅ FIX PRINCIPAL : Si une disponibilité globale existe, TOUS les juristes sont dispos
    if global_availabilities:
        return True

    # Si pas de disponibilité globale, vérifier les disponibilités spécifiques
    if jurist:
        specific_availabilities = JuristGlobalAvailability.objects.filter(
            Q(date=day) | Q(repeat_weekly=True, date__week_day=django_weekday),
            availability_type='specific',
            jurist=jurist,
            is_active=True
        ).exists()
        return specific_availabilities

    return False


def get_slots_for_day(day, jurist=None):
    """
    ✅ CORRECTION : Gère correctement les disponibilités globales et spécifiques

    Retourne TOUS les créneaux (aware, Europe/Paris) pour le jour donné.

    Logique:
    - Les créneaux globaux sont disponibles pour TOUS les juristes
    - Les créneaux spécifiques sont disponibles uniquement pour le juriste assigné
    """
    tz = get_current_timezone()
    slots = []

    # Conversion correcte du jour de la semaine
    django_weekday = (day.weekday() + 2) % 7
    if django_weekday == 0:
        django_weekday = 7

    # Construire la requête pour les disponibilités
    base_query = Q(date=day) | Q(repeat_weekly=True, date__week_day=django_weekday)
    base_query &= Q(is_active=True)

    if jurist:
        # ✅ Pour un juriste spécifique : disponibilités globales + ses disponibilités spécifiques
        availabilities = JuristGlobalAvailability.objects.filter(
            base_query & (
                    Q(availability_type='global') |
                    Q(availability_type='specific', jurist=jurist)
            )
        )
    else:
        # Pour tous les juristes : uniquement les disponibilités globales
        availabilities = JuristGlobalAvailability.objects.filter(
            base_query & Q(availability_type='global')
        )

    for avail in availabilities:
        hstart, hend = avail.start_time, avail.end_time
        slot_duration = timedelta(minutes=avail.slot_duration)

        current = datetime.combine(day, hstart)
        end_dt = datetime.combine(day, hend)

        # Boucle sur la plage avec la durée de créneau spécifique
        while current + slot_duration <= end_dt:
            aware_slot = make_aware(current, timezone=tz)
            slots.append({
                'time': aware_slot,
                'duration_minutes': avail.slot_duration,
                'availability_type': avail.availability_type,
                'jurist_specific': avail.jurist_id if avail.availability_type == 'specific' else None
            })
            current += slot_duration

    return slots


def get_available_slots_for_jurist(jurist, day):
    """
    ✅ CORRECTION : Prend en compte les disponibilités globales

    Retourne les créneaux disponibles (au format ISO string) pour ce juriste et ce jour.

    Logique:
    1. Vérifier si le jour a des disponibilités (globales OU spécifiques au juriste)
    2. Récupérer tous les créneaux possibles (globaux + spécifiques)
    3. Exclure les créneaux déjà réservés par ce juriste
    """
    # Vérifier d'abord s'il y a des disponibilités pour ce jour
    if not is_valid_day(day, jurist):
        return []

    # Récupérer tous les créneaux possibles pour ce juriste
    # (créneaux globaux + créneaux spécifiques à ce juriste)
    all_slots_data = get_slots_for_day(day, jurist)

    # Récupérer les créneaux déjà pris par CE juriste
    taken_slots = set(
        JuristAppointment.objects.filter(
            jurist=jurist,
            date__date=day
        ).values_list("date", flat=True)
    )

    # Filtrer les créneaux disponibles
    available_slots = []
    for slot_data in all_slots_data:
        slot_time = slot_data['time']
        if slot_time not in taken_slots:
            available_slots.append({
                'start_time': slot_time.isoformat(),
                'duration_minutes': slot_data['duration_minutes'],
                'availability_type': slot_data['availability_type']
            })

    return available_slots


def get_available_slots_for_global(day):
    """
    Retourne les créneaux disponibles globaux (sans juriste spécifique)
    """
    if not is_valid_day(day):
        return []

    all_slots_data = get_slots_for_day(day)

    # Pour les créneaux globaux, on veut tous les créneaux non assignés à un juriste spécifique
    global_slots = [
        slot for slot in all_slots_data
        if slot['availability_type'] == 'global'
    ]

    return [{
        'start_time': slot['time'].isoformat(),
        'duration_minutes': slot['duration_minutes'],
        'availability_type': slot['availability_type']
    } for slot in global_slots]