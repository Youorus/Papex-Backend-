from .client import OVHClient
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class PhoneSender:
    def __init__(self):
        self.client = OVHClient.get_client()
        self.billing_account = settings.OVH_PHONE_BILLING_ACCOUNT
        self.line_identifier = settings.OVH_PHONE_SIP_LINE  # ex: 0033185099755

    def click_to_call(self, destination_number: str):
        try:
            logger.info(
                f"📞 Click2Call | line={self.line_identifier} → {destination_number}"
            )

            response = self.client.post(
                f"/telephony/{self.billing_account}/line/{self.line_identifier}/click2Call",
                calledNumber=destination_number
            )

            logger.info(f"✅ OVH Click2Call OK: {response}")
            return {"success": True, "data": response}

        except Exception as e:
            logger.exception("❌ OVH Click2Call ERROR")
            return {"success": False, "error": str(e)}


