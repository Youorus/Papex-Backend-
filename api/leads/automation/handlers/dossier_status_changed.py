import logging
from api.utils.email.leads.tasks import (
    send_dossier_status_notification_task
)
from api.sms.tasks import send_dossier_status_updated_sms_task

logger = logging.getLogger(__name__)


import logging
from api.utils.email.leads.tasks import (
    send_dossier_status_notification_task
)
from api.sms.tasks import send_dossier_status_updated_sms_task

logger = logging.getLogger(__name__)


def handle_dossier_status_changed(event):
    """
    Handler déclenché lors d'un changement de statut dossier.
    """

    lead = event.lead

    # ✅ CORRECTION ICI
    data = event.data or {}
    new_status = data.get("to")

    if not lead:
        return

    # --------------------------
    # 📧 EMAIL
    # --------------------------
    if lead.email:
        send_dossier_status_notification_task(lead.id)


    # --------------------------
    # 🧾 LOG
    # --------------------------
    logger.info(
        "📁 Lead #%s statut dossier → %s (email + sms déclenchés)",
        lead.id,
        new_status,
    )