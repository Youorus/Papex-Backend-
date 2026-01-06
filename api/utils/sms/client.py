# api/utils/sms/client.py

import ovh
from django.conf import settings


def get_ovh_client() -> ovh.Client:
    return ovh.Client(
        endpoint="ovh-eu",
        application_key=settings.APP_KEY,
        application_secret=settings.APP_SECRET,
        consumer_key=settings.CONSUMER_KEY,
    )
