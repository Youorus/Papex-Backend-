from datetime import date

import pytest

from api.clients.models import Client
from api.lead_status.models import LeadStatus
from api.leads.models import Lead
from api.services.models import Service

pytestmark = pytest.mark.django_db


@pytest.fixture
def default_status():
    return LeadStatus.objects.create(code="NOUVEAU", label="Nouveau", color="#0000FF")


def test_client_minimal_creation(default_status):
    lead = Lead.objects.create(
        first_name="John", last_name="Doe", status=default_status
    )
    client = Client.objects.create(lead=lead)

    assert client.pk is not None
    assert client.lead.first_name == "John"
    assert client.lead.last_name == "Doe"


def test_client_complet_creation(default_status):
    lead = Lead.objects.create(
        first_name="Alice", last_name="Martin", status=default_status
    )
    service = Service.objects.create(
        code="TITRE_SEJOUR", label="Titre de séjour", price=120
    )

    client = Client.objects.create(
        lead=lead,
        has_anef_account=True,
        anef_email="alice@exemple.com",
        anef_password="123456",
        source=["ami", "reseaux_sociaux"],
        civilite="MLLE",
        date_naissance=date(1990, 1, 1),
        lieu_naissance="Toulouse",
        pays="France",
        nationalite="française",
        adresse="1 rue de la paix",
        code_postal="31000",
        ville="Toulouse",
        date_entree_france=date(2010, 5, 10),
        type_demande=service,
        custom_demande="Naturalisation",
        demande_deja_formulee=True,
        demande_formulee_precise="Demande ANEF en attente",
        a_un_visa=True,
        type_visa="ETUDIANT",
        statut_refugie_ou_protection=False,
        situation_familiale="CELIBATAIRE",
        a_des_enfants=False,
        nombre_enfants=0,
        nombre_enfants_francais=0,
        enfants_scolarises=False,
        naissance_enfants_details="N/A",
        situation_pro="ETUDIANT",
        domaine_activite="Informatique",
        nombre_fiches_paie=3,
        date_depuis_sans_emploi=date(2023, 1, 1),
        logement_type="CHEZ_TIERS",
        a_deja_eu_oqtf=False,
        date_derniere_oqtf=None,
        demarche_en_cours_administration=True,
        remarques="Rendez-vous pris pour dépôt du dossier.",
    )

    assert client.ville == "Toulouse"
    assert client.civilite == "MLLE"
    assert client.type_demande == service
    assert isinstance(client.source, list)


def test_client_str(default_status):
    lead = Lead.objects.create(
        first_name="Fatou", last_name="Ndoye", status=default_status
    )
    client = Client.objects.create(lead=lead)
    assert str(client) == "Données de Fatou Ndoye"
