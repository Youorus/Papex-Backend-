import ovh
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class OVHClient:
    _instance = None

    @classmethod
    def get_client(cls):
        if cls._instance is None:
            app_key = getattr(settings, "OVH_PHONE_APP_KEY", None)
            app_secret = getattr(settings, "OVH_PHONE_APP_SECRET", None)
            consumer_key = getattr(settings, "OVH_PHONE_CONSUMER_KEY", None)

            if not all([app_key, app_secret, consumer_key]):
                raise ImproperlyConfigured(
                    "Les variables OVH_PHONE_APP_KEY / OVH_PHONE_APP_SECRET / "
                    "OVH_PHONE_CONSUMER_KEY ne sont pas définies dans settings.py"
                )

            cls._instance = ovh.Client(
                endpoint="ovh-eu",
                application_key=app_key,
                application_secret=app_secret,
                consumer_key=consumer_key,
            )

        return cls._instance
