# api/utils/email/utils.py

from datetime import datetime
from dateutil import tz


def get_french_datetime_strings_sms(dt: datetime):
    """
    Retourne une date et une heure SMS-friendly en français.

    Exemples:
    - date_str: "19/02/2024"  (format dd/mm/YYYY)
    - time_str: "16h30"
    """

    if not isinstance(dt, datetime):
        raise ValueError("dt must be a datetime")

    # Timezone France
    france_tz = tz.gettz("Europe/Paris")
    dt = dt.astimezone(france_tz)

    # Format date: dd/mm/YYYY
    date_str = f"{dt:%d/%m/%Y}"  # 19/02/2024
    time_str = f"{dt:%H}h{dt:%M}"  # 16h30

    return date_str, time_str