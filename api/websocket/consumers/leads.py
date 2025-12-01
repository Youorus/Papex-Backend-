# consumers/leads.py

from .base import BaseConsumer
import logging

logger = logging.getLogger(__name__)

class LeadConsumer(BaseConsumer):
    group_prefix = "leads"

    def get_group_name(self, **kwargs):
        lead_id = kwargs.get("lead_id")
        if not lead_id:
            logger.warning("⚠️ Connexion au groupe général 'leads' car aucun 'lead_id' fourni")
            return self.group_prefix  # fallback: leads
        return f"{self.group_prefix}_{lead_id}"