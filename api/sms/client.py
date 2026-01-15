# api/utils/sms/client.py

import ovh
from django.conf import settings


def get_ovh_sms_client() -> ovh.Client:
    return ovh.Client(
        endpoint="ovh-eu",
        application_key=settings.OVH_SMS_APP_KEY,
        application_secret=settings.OVH_SMS_APP_SECRET,
        consumer_key=settings.OVH_SMS_CONSUMER_KEY,
    )
