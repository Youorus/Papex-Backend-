# api/utils/sms/sender.py

import logging
import ovh
from django.conf import settings

from .client import get_ovh_sms_client

logger = logging.getLogger(__name__)


def send_sms(
    *,
    message: str,
    receivers: list[str],
    sender: str | None = None,
):
    if not receivers:
        logger.warning("📵 Aucun destinataire SMS fourni")
        return

    client = get_ovh_sms_client()

    try:
        result = client.post(
            f"/sms/{settings.OVH_SMS_SERVICE_NAME}/jobs",
            sender=sender or settings.OVH_SMS_SENDER,
            message=message,
            receivers=receivers,
        )

        logger.info(
            f"📲 SMS envoyé à {receivers} — job={result.get('id')}"
        )
        return result

    except ovh.exceptions.APIError as e:
        logger.error(f"❌ Erreur OVH SMS : {e}")
        raise
