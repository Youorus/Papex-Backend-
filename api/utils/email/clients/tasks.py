import logging

from celery import shared_task

from api.utils.email.clients.notifications import send_client_account_created_email

logger = logging.getLogger(__name__)


@shared_task
def send_client_account_created_task(client_id: int):
    from api.clients.models import Client  # import inside to avoid circular imports

    client = Client.objects.select_related("lead").filter(id=client_id).first()
    if client and client.lead and client.lead.email:
        send_client_account_created_email(client)
        logger.info(
            f"👤 E-mail de création de compte client envoyé à {client.lead.email} (client #{client.id})"
        )
    else:
        logger.warning(
            f"❌ E-mail non envoyé – client #{client_id} introuvable ou lead/email manquant"
        )
