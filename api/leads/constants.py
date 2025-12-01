# leads/constants.py

# Centralisation des codes de statut pour robustesse et facilité de maintenance

RDV_CONFIRME = "RDV_CONFIRME"
RDV_PLANIFIE = "RDV_PLANIFIE"
ABSENT = "ABSENT"
PRESENT = "PRESENT"

# Utilisable partout : import {RDV_CONFIRME, ...} from leads.constants
LEAD_STATUS_CODES = [
    RDV_CONFIRME,
    RDV_PLANIFIE,
    ABSENT,
    PRESENT,
]
