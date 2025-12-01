import pytest

"""
Tests unitaires pour le serializer LeadSerializer.

Objectifs :
- Vérifier la validité des données selon différents scénarios (email invalide, doublons, etc.)
- Vérifier les comportements conditionnels (ex : champ appointment_date requis selon le statut)
- Tester la logique de transformation des champs (ex : mise en majuscule, formatage de date)
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from rest_framework.exceptions import ValidationError

from api.lead_status.models import LeadStatus
from api.leads.constants import RDV_CONFIRME, RDV_PLANIFIE
from api.leads.models import Lead
from api.leads.serializers import LeadSerializer
from api.statut_dossier.models import StatutDossier
from api.users.models import User
from api.users.roles import UserRoles

pytestmark = pytest.mark.django_db


@pytest.fixture
def status_planifie():
    return LeadStatus.objects.create(code=RDV_PLANIFIE, label="Planifié")


@pytest.fixture
def status_confirme():
    return LeadStatus.objects.create(code=RDV_CONFIRME, label="Confirmé")


@pytest.fixture
def conseiller():
    return User.objects.create_user(
        email="conseiller@test.com", password="123", role=UserRoles.CONSEILLER
    )


@pytest.fixture
def juriste():
    return User.objects.create_user(
        email="juriste@test.com", password="123", role=UserRoles.JURISTE
    )


@pytest.fixture
def dossier():
    return StatutDossier.objects.create(
        code="COMPLET", label="Dossier complet", role=UserRoles.ADMIN
    )


def test_valid_serializer(status_planifie):
    data = {
        "first_name": "Jean",
        "last_name": "Dupont",
        "phone": "+33600000000",
        "email": "jean@example.com",
        "status_id": status_planifie.id,
        "appointment_date": "26/08/2025 10:30",
    }
    serializer = LeadSerializer(data=data)
    assert serializer.is_valid(), serializer.errors


def test_invalid_email_format(status_planifie):
    data = {
        "first_name": "Marie",
        "last_name": "Curie",
        "phone": "+33612345678",
        "email": "invalid-email",
        "status_id": status_planifie.id,
    }
    serializer = LeadSerializer(data=data)
    assert not serializer.is_valid()
    assert "email" in serializer.errors


def test_email_already_used(status_planifie):
    Lead.objects.create(
        first_name="Alice",
        last_name="Dupuis",
        phone="+33699999999",
        email="used@example.com",
        status=status_planifie,
    )
    data = {
        "first_name": "Bob",
        "last_name": "Dupont",
        "phone": "+33677777777",
        "email": "used@example.com",
        "status_id": status_planifie.id,
    }
    serializer = LeadSerializer(data=data)
    assert not serializer.is_valid()
    assert "email" in serializer.errors


def test_first_name_capitalized(status_planifie):
    data = {
        "first_name": "julie",
        "last_name": "bernard",
        "phone": "+33688888888",
        "email": "julie@example.com",
        "status_id": status_planifie.id,
        "appointment_date": "26/08/2025 10:30",
    }
    serializer = LeadSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    assert serializer.validated_data["first_name"] == "Julie"
    assert serializer.validated_data["last_name"] == "Bernard"


def test_rdv_required_for_status_confirme(status_confirme):
    data = {
        "first_name": "Claire",
        "last_name": "Martin",
        "phone": "+33600000000",
        "email": "claire@example.com",
        "status_id": status_confirme.id,
    }
    serializer = LeadSerializer(data=data)
    with pytest.raises(ValidationError) as exc_info:
        serializer.is_valid(raise_exception=True)
    assert "appointment_date" in str(exc_info.value)


def test_valid_appointment_date_format(status_confirme):
    data = {
        "first_name": "Éric",
        "last_name": "Tremblay",
        "phone": "+33600000001",
        "email": "eric@example.com",
        "status_id": status_confirme.id,
        "appointment_date": "26/08/2025 10:30",
    }
    serializer = LeadSerializer(data=data)
    assert serializer.is_valid()


def test_to_representation_formats_datetime(status_planifie):
    dt_utc = datetime(2025, 8, 26, 8, 0, tzinfo=ZoneInfo("UTC"))
    lead = Lead.objects.create(
        first_name="Paul",
        last_name="Durand",
        phone="+336",
        email="p@ex.com",
        status=status_planifie,
        appointment_date=dt_utc,
    )
    serialized = LeadSerializer(lead).data
    assert serialized["appointment_date"] == "26/08/2025 10:00"


def test_contract_emitter_id_returns_none(status_planifie):
    lead = Lead.objects.create(
        first_name="No",
        last_name="Client",
        phone="+336",
        email="noclient@ex.com",
        status=status_planifie,
    )
    serializer = LeadSerializer(lead)
    assert serializer.data["contract_emitter_id"] is None
