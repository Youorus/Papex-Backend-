from babel.dates import format_datetime
from django.utils import timezone


def get_french_datetime_strings(dt):
    """Retourne une date et heure localisée en français."""
    dt_local = timezone.localtime(dt)
    return (
        format_datetime(dt_local, "EEEE d MMMM yyyy", locale="fr_FR"),
        format_datetime(dt_local, "HH:mm", locale="fr_FR"),
    )


def _name_from_user(user) -> str | None:
    """Construit un nom affichable."""
    if not user:
        return None
    first = (getattr(user, "first_name", "") or "").strip()
    last = (getattr(user, "last_name", "") or "").strip()
    return (
        f"{first} {last}".strip()
        or getattr(user, "username", None)
        or getattr(user, "email", None)
    )


def _get_with_info(appointment) -> tuple[str | None, str | None]:
    """Retourne (label, nom) de la personne liée au rendez-vous."""
    user, label = None, None

    if hasattr(appointment, "jurist") and appointment.jurist:
        user, label = appointment.jurist, "Juriste"
    elif hasattr(appointment, "created_by") and appointment.created_by:
        user, label = appointment.created_by, "Conseiller"
    elif hasattr(appointment, "lead") and appointment.lead.assigned_to:
        user, label = appointment.lead.assigned_to, "Conseiller"

    return label, _name_from_user(user)
