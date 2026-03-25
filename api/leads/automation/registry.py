# api/automations/registry.py

from .handlers.lead_created import handle_lead_created
from .handlers.status_changed import handle_status_changed

# CONTRACTS
from .handlers.contract_signed import handle_contract_signed

from .handlers.contract_sent import handle_contract_email_sent

from .handlers.receipt_sent import handle_receipts_email_sent

# DOSSIER
from .handlers.dossier_status_changed import handle_dossier_status_changed

# RECEIPTS


AUTOMATION_REGISTRY = {
    # ============================================================
    # LEADS
    # ============================================================
    "LEAD_CREATED": [
        handle_lead_created,
    ],

    "STATUS_CHANGED": [
        handle_status_changed,
    ],

    # ============================================================
    # CONTRACTS
    # ============================================================
    "CONTRACT_EMAIL_SENT": [
        handle_contract_email_sent
    ],

    "CONTRACT_SIGNED": [
        handle_contract_signed,
    ],

    # ============================================================
    # DOSSIER
    # ============================================================
    "DOSSIER_STATUS_CHANGED": [
        handle_dossier_status_changed,
    ],

    # ============================================================
    # RECEIPTS
    # ============================================================
    "RECEIPTS_EMAIL_SENT": [
        handle_receipts_email_sent,
    ],
}