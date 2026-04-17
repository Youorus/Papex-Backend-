from typing import Optional, Dict, Any

from api.clients.models import Client
from api.leads.models import Lead
from api.leads_events.models import LeadEvent


def create_lead_with_side_effects(
    *,
    actor,
    event_source: str,
    lead_kwargs: Dict[str, Any],
    event_data: Optional[Dict[str, Any]] = None,
):
    lead = Lead.objects.create(**lead_kwargs)

    Client.objects.get_or_create(lead=lead)

    LeadEvent.log(
        lead=lead,
        event_code="LEAD_CREATED",
        actor=actor,
        data={
            "source": event_source,
            **(event_data or {}),
        },
    )

    return lead