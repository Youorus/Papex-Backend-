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
    """
    Envoie un SMS via l'API OVH et logue la réponse complète pour le débugging.
    """
    if not receivers:
        logger.warning("📵 Aucun destinataire SMS fourni")
        return

    client = get_ovh_sms_client()
    service_name = settings.OVH_SMS_SERVICE_NAME
    sender_id = sender or settings.OVH_SMS_SENDER

    try:
        # 1. Tentative d'envoi
        result = client.post(
            f"/sms/{service_name}/jobs",
            sender=sender_id,
            message=message,
            receivers=receivers,
            noStopClause=False,  # Mettre à True si vous gérez le STOP vous-même
        )

        # 2. DEBUG : On logue la réponse brute d'OVH pour voir les erreurs cachées
        # C'est ici que tu verras si 'totalCreditsRemoved' est à 0
        logger.info(f"🔍 DEBUG BRUT OVH : {result}")

        # 3. Récupération intelligente de l'ID (OVH renvoie souvent une liste 'ids')
        job_ids = result.get('ids', [])
        job_id = job_ids[0] if job_ids else result.get('id')

        logger.info(
            f"📲 SMS envoyé à {receivers} — job={job_id} — "
            f"Crédits retirés: {result.get('totalCreditsRemoved', 'N/A')}"
        )

        return result

    except ovh.exceptions.APIError as e:
        # Capturer spécifiquement les erreurs d'API (crédits, sender invalide, etc.)
        logger.error(f"❌ Erreur critique API OVH SMS : {e}")
        raise
    except Exception as e:
        logger.error(f"❌ Erreur inattendue lors de l'envoi SMS : {e}")
        raise