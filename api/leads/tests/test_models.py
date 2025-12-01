"""
Tests unitaires pour les modèles liés aux leads.

Ce fichier contient des tests de validation pour :
- L’affichage de la représentation textuelle d’un lead.
- Le comportement du statut par défaut lors de la création d’un lead.
- Le maintien du statut confirmé lorsqu’un rendez-vous est présent.
"""

import pytest
from django.utils import timezone

from api.lead_status.models import LeadStatus
from api.leads.constants import RDV_CONFIRME, RDV_PLANIFIE
from api.leads.models import Lead

pytestmark = pytest.mark.django_db


def test_lead_str_affichage():
    status = LeadStatus.objects.create(code=RDV_PLANIFIE, label="Planifié")
    lead = Lead.objects.create(
        first_name="Alice", last_name="Durand", phone="+33612345678", status=status
    )
    assert str(lead) == "Alice Durand - Planifié"


def test_statut_defaut_est_defini_si_absent():
    statut_defaut = LeadStatus.objects.create(code=RDV_PLANIFIE, label="Planifié")
    lead = Lead.objects.create(
        first_name="Bob", last_name="Martin", phone="+33600000000", status=statut_defaut
    )
    assert lead.status.code == RDV_PLANIFIE


def test_statut_reste_confirme_si_rdv_present():
    statut_rdv_confirme = LeadStatus.objects.create(code=RDV_CONFIRME, label="Confirmé")
    rdv = timezone.now()
    lead = Lead.objects.create(
        first_name="Chloé",
        last_name="Bernard",
        phone="+33611111111",
        appointment_date=rdv,
        status=statut_rdv_confirme,
    )
    assert lead.status.code == RDV_CONFIRME
