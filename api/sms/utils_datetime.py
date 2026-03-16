# api/sms/utils_datetime.py

from datetime import datetime
from dateutil import tz


def get_french_datetime_strings_sms(dt: datetime) -> tuple[str, str]:
    """
    Convertit un datetime (UTC ou naïf) en strings SMS-friendly
    localisées sur le fuseau Europe/Paris.

    Retourne :
        date_str : "19/02/2024"   (format dd/mm/YYYY)
        time_str : "16h30"

    Raises :
        ValueError si dt n'est pas un datetime.
    """
    if not isinstance(dt, datetime):
        raise ValueError(f"dt doit être un datetime, reçu : {type(dt)}")

    france_tz = tz.gettz("Europe/Paris")
    dt = dt.astimezone(france_tz)

    date_str = f"{dt:%d/%m/%Y}"
    time_str = f"{dt:%H}h{dt:%M}"

    return date_str, time_str