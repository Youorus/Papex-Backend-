import requests
from babel.dates import format_datetime
from django.utils import timezone


def get_formatted_appointment(dt):
    if not dt:
        return {"date": "Non précisée", "time": "Non précisée"}

    local_dt = timezone.localtime(dt)

    return {
        "date": format_datetime(
            local_dt, "EEEE d MMMM y", locale="fr"
        ).capitalize(),  # ex: lundi 10 avril 2025
        "time": format_datetime(local_dt, "HH:mm", locale="fr"),  # ex: 14:30
    }


def download_file(url):
    import os

    import requests

    response = requests.get(url)
    response.raise_for_status()
    content = response.content
    filename = os.path.basename(url)
    return content, filename


def get_french_datetime_strings(dt):
    dt_local = timezone.localtime(dt)
    # Le format Babel, pas strftime !
    date_str = format_datetime(dt_local, "EEEE d MMMM yyyy", locale="fr_FR")
    time_str = format_datetime(dt_local, "HH:mm", locale="fr_FR")
    return date_str, time_str
