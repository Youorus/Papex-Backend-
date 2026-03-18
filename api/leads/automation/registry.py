# api/leads/automation/registry.py

from .handlers.lead_created import handle_lead_created
from .handlers.status_changed import handle_status_changed
from .handlers.contract_signed import handle_contract_signed

AUTOMATION_REGISTRY = {
    "LEAD_CREATED":     [handle_lead_created],
    "STATUS_CHANGED":   [handle_status_changed],
    "CONTRACT_SIGNED": [handle_contract_signed],
}