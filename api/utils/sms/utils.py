# api/utils/email/utils.py

from datetime import datetime
from dateutil import tz


def get_french_datetime_strings_sms(dt: datetime):
    """
    Retourne une date et une heure SMS-friendly en francais.

    Exemples:
    - date_str: "Ven. 19/02"
    - time_str: "16h30"
    """

    if not isinstance(dt, datetime):
        raise ValueError("dt must be a datetime")

    # Timezone France
    france_tz = tz.gettz("Europe/Paris")
    dt = dt.astimezone(france_tz)

    # Jours FR courts (sans accents)
    days = ["Lun.", "Mar.", "Mer.", "Jeu.", "Ven.", "Sam.", "Dim."]

    day_str = days[dt.weekday()]          # Ven.
    date_str = f"{day_str} {dt:%d/%m}"    # Ven. 19/02
    time_str = f"{dt:%H}h{dt:%M}"          # 16h30

    return date_str, time_str