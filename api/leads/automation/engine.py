import logging
from api.leads.automation.registry import AUTOMATION_REGISTRY

logger = logging.getLogger(__name__)


class AutomationEngine:

    @classmethod
    def handle(cls, event):

        logger.info(
            "[AutomationEngine] Événement reçu : code=%s | lead_id=%s",
            event.event_type.code,
            event.lead_id,
        )

        handlers = AUTOMATION_REGISTRY.get(event.event_type.code, [])

        if not handlers:
            logger.warning(
                "[AutomationEngine] Aucun handler trouvé pour l'événement : %s",
                event.event_type.code,
            )
            return

        for handler in handlers:
            logger.debug(
                "[AutomationEngine] Exécution du handler : %s",
                handler.__name__,
            )
            handler(event)

        logger.info(
            "[AutomationEngine] %d handler(s) exécuté(s) pour l'événement %s",
            len(handlers),
            event.event_type.code,
        )