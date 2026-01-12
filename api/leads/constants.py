# leads/constants.py

# Centralisation des codes de statut pour robustesse et facilité de maintenance

RDV_A_CONFIRMER = "RDV_A_CONFIRMER"
RDV_CONFIRME = "RDV_CONFIRME"
RDV_PLANIFIE = "RDV_PLANIFIE"  # legacy / optionnel
A_RAPPELER = "A_RAPPELER"
ABSENT = "ABSENT"
PRESENT = "PRESENT"

# Utilisable partout : import {RDV_CONFIRME, ...} from leads.constants
LEAD_STATUS_CODES = [
    RDV_A_CONFIRMER,
    A_RAPPELER,
    RDV_CONFIRME,
    RDV_PLANIFIE,
    ABSENT,
    PRESENT,
]


RDV_PRESENTIEL = "PRESENTIEL"
RDV_TELEPHONE = "TELEPHONE"
RDV_VISIO_CONFERENCE = "VISIO_CONFERENCE"

APPOINTMENT_TYPE_CHOICES = [
    (RDV_PRESENTIEL, "Présentiel"),
    (RDV_TELEPHONE, "Téléphonique"),
    (RDV_VISIO_CONFERENCE, "Visio-conférence"),
]
