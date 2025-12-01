# consumers/clients.py
import logging
from .base import BaseConsumer

logger = logging.getLogger(__name__)

class ClientRoomConsumer(BaseConsumer):
    """
    Consumer WebSocket pour gérer les rooms liées à un client donné.
    Chaque client_id correspond à un groupe distinct : client-<id>.
    """
    group_prefix = "client"

    def get_group_name(self) -> str:
        """
        Génère le nom du groupe basé sur le client_id extrait de l'URL.
        Exemple : client-19
        """
        try:
            client_id = int(self.scope["url_route"]["kwargs"].get("client_id"))
            return f"{self.group_prefix}-{client_id}"
        except (KeyError, TypeError, ValueError):
            logger.error("❌ client_id invalide dans l’URL de connexion WebSocket")
            raise ValueError("client_id invalide pour la connexion WebSocket")
        except Exception as e:
            logger.exception(f"❌ Erreur inattendue lors du group_name (client) : {str(e)}")
            raise