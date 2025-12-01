from datetime import date, timedelta

import pytest
from rest_framework.exceptions import ValidationError

from api.clients.serializers import ClientSerializer
from api.leads.models import Lead
from api.services.models import Service


@pytest.mark.django_db
def test_valid_client_serializer():
    from api.lead_status.models import LeadStatus
    from api.services.models import Service

    status = LeadStatus.objects.create(code="NOUVEAU", label="Nouveau", color="#0000FF")
    lead = Lead.objects.create(first_name="Alice", last_name="Dupont", status=status)

    service = Service.objects.create(
        code="TITRE_SEJOUR",
        label="Titre de séjour",
        price=100,
    )

    data = {
        "type_demande_id": service.id,
        "date_naissance": "1990-01-01",
        "date_entree_france": "2010-01-01",
        "adresse": "123 rue Lafayette",
        "code_postal": "75010",
        "ville": "Paris",
        "nombre_enfants": 2,
        "nombre_enfants_francais": 1,
        "nombre_fiches_paie": 3,
    }

    serializer = ClientSerializer(data=data)
    serializer.context["lead"] = lead
    assert serializer.is_valid(), serializer.errors


@pytest.mark.django_db
def test_invalid_date_naissance_future():
    data = {
        "date_naissance": date.today() + timedelta(days=1),
    }
    serializer = ClientSerializer(data=data)
    with pytest.raises(ValidationError) as e:
        serializer.is_valid(raise_exception=True)
    assert "date_naissance" in str(e.value)


@pytest.mark.django_db
def test_invalid_code_postal_length():
    data = {
        "code_postal": "abc",
    }
    serializer = ClientSerializer(data=data)
    with pytest.raises(ValidationError) as e:
        serializer.is_valid(raise_exception=True)
    assert "code_postal" in str(e.value)


@pytest.mark.django_db
def test_cross_field_validation_visa_type_required():
    data = {
        "a_un_visa": True,
        "type_visa": None,
    }
    serializer = ClientSerializer(data=data)
    with pytest.raises(ValidationError) as e:
        serializer.is_valid(raise_exception=True)
    assert "type_visa" in str(e.value)


@pytest.mark.django_db
def test_cross_field_validation_negative_values():
    data = {
        "nombre_enfants": -1,
        "nombre_enfants_francais": -1,
        "nombre_fiches_paie": -1,
    }
    serializer = ClientSerializer(data=data)
    with pytest.raises(ValidationError) as e:
        serializer.is_valid(raise_exception=True)
    assert "nombre_enfants" in str(e.value)
    assert "nombre_enfants_francais" in str(e.value)
    assert "nombre_fiches_paie" in str(e.value)
