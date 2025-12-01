"""
Tests fonctionnels pour la vue personnalisée `LeadSearchView`.

Ces tests couvrent :
- Les méthodes internes de parsing et de transformation utilisées par la recherche avancée.
- Les filtres disponibles (statut du lead, statut du dossier, juriste assigné, conseiller assigné).
- Le tri (`ordering`) et la pagination des résultats.
- L’authentification de l’utilisateur.

Tous les tests utilisent un `APIClient` authentifié avec un utilisateur ADMIN.
"""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from api.lead_status.models import LeadStatus
from api.leads.constants import RDV_CONFIRME, RDV_PLANIFIE
from api.leads.lead_search import (
    _normalize_avec_sans,
    _parse_iso_any,
    _to_aware,
    _to_int_or_none,
)
from api.leads.models import Lead
from api.statut_dossier.models import StatutDossier
from api.users.models import User
from api.users.roles import UserRoles

pytestmark = pytest.mark.django_db


@pytest.fixture
def authenticated_client():
    user = User.objects.create_user(
        email="test@example.com",
        password="pass",
        role=UserRoles.ADMIN,
        first_name="Admin",
        last_name="Test",
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def lead_status():
    return LeadStatus.objects.create(code=RDV_PLANIFIE, label="Planifié")


@pytest.fixture
def lead_status_confirme():
    return LeadStatus.objects.create(code=RDV_CONFIRME, label="Confirmé")


@pytest.fixture
def statut_dossier():
    return StatutDossier.objects.create(code="A_TRAITER", label="À traiter")


def test_parse_iso_any_date_and_datetime():
    assert _parse_iso_any("2025-08-25") is not None
    assert _parse_iso_any("2025-08-25T10:30:00") is not None
    assert _parse_iso_any("") is None
    assert _parse_iso_any(None) is None


def test_to_aware_converts_naive_date():
    from datetime import date

    aware = _to_aware(date(2025, 8, 26))
    assert aware.tzinfo is not None


def test_normalize_avec_sans_variants():
    assert _normalize_avec_sans("oui") == "avec"
    assert _normalize_avec_sans("false") == "sans"
    assert _normalize_avec_sans("autre") is None


def test_to_int_or_none_behavior():
    assert _to_int_or_none("42") == 42
    assert _to_int_or_none("abc") is None
    assert _to_int_or_none(None) is None


def test_filter_by_status_code(authenticated_client, lead_status):
    Lead.objects.create(
        first_name="A",
        last_name="X",
        phone="+1",
        email="a@test.com",
        status=lead_status,
    )
    url = reverse("lead-search") + f"?status_code={lead_status.code}"
    res = authenticated_client.get(url)
    assert res.status_code == 200
    assert res.data["total"] == 1


def test_filter_by_status_id(authenticated_client, lead_status):
    Lead.objects.create(
        first_name="B",
        last_name="Y",
        phone="+2",
        email="b@test.com",
        status=lead_status,
    )
    url = reverse("lead-search") + f"?status_id={lead_status.id}"
    res = authenticated_client.get(url)
    assert res.status_code == 200
    assert res.data["total"] == 1


def test_filter_by_dossier_code(authenticated_client, lead_status, statut_dossier):
    Lead.objects.create(
        first_name="C",
        last_name="Z",
        phone="+3",
        email="c@test.com",
        status=lead_status,
        statut_dossier=statut_dossier,
    )
    url = reverse("lead-search") + f"?dossier_code={statut_dossier.code}"
    res = authenticated_client.get(url)
    assert res.status_code == 200
    assert res.data["total"] == 1


def test_filter_has_jurist(authenticated_client, lead_status):
    jurist = User.objects.create_user(
        email="j@ex.com",
        password="pass",
        role=UserRoles.JURISTE,
        first_name="Juriste",
        last_name="Ex",
    )
    lead = Lead.objects.create(
        first_name="D",
        last_name="Z",
        phone="+4",
        email="d@test.com",
        status=lead_status,
    )
    lead.jurist_assigned.add(jurist)

    url = reverse("lead-search") + "?has_jurist=avec"
    res = authenticated_client.get(url)
    assert res.status_code == 200
    assert res.data["total"] == 1


def test_filter_has_conseiller(authenticated_client, lead_status):
    conseiller = User.objects.create_user(
        email="c@ex.com",
        password="pass",
        role=UserRoles.CONSEILLER,
        first_name="Conseiller",
        last_name="Ex",
    )
    lead = Lead.objects.create(
        first_name="E",
        last_name="F",
        phone="+5",
        email="e@test.com",
        status=lead_status,
    )
    lead.assigned_to.add(conseiller)

    url = reverse("lead-search") + "?has_conseiller=avec"
    res = authenticated_client.get(url)
    assert res.status_code == 200
    assert res.data["total"] == 1


def test_ordering_and_pagination(authenticated_client, lead_status):
    Lead.objects.create(
        first_name="A", last_name="A", phone="+1", email="a@x.com", status=lead_status
    )
    Lead.objects.create(
        first_name="B", last_name="B", phone="+2", email="b@x.com", status=lead_status
    )

    url = reverse("lead-search") + "?ordering=created_at&page=1&page_size=1"
    res = authenticated_client.get(url)
    assert res.status_code == 200
    assert res.data["page"] == 1
    assert res.data["page_size"] == 1
    assert res.data["total"] >= 2
