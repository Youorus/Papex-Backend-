from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils.timezone import now, timedelta
from rest_framework import status
from rest_framework.test import APIClient

from api.clients.models import Client
from api.contracts.models import Contract
from api.leads.models import Lead, LeadStatus
from api.payments.models import PaymentReceipt
from api.services.models import Service
from api.users.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return User.objects.create_user(
        email="admin@tds.fr",
        password="admin123",
        role="ADMIN",
        first_name="Admin",
        last_name="Test",
    )


@pytest.fixture
def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def setup_contracts(user):
    # Création d’un statut de lead valide
    status = LeadStatus.objects.create(code="NOUVEAU", label="Nouveau", color="#0ea5e9")

    # Création d’un lead avec ce statut
    lead = Lead.objects.create(
        first_name="Marc",
        last_name="Test",
        email="marc@test.fr",
        phone="0612345678",
        status=status,
    )

    # Client lié à ce lead
    client = Client.objects.create(lead=lead)

    # Service de test
    service = Service.objects.create(code="VISA", label="Visa Étudiant", price=200)

    # Contrat 1 : payé intégralement
    contract1 = Contract.objects.create(
        client=client,
        created_by=user,
        service=service,
        amount_due=200,
        is_signed=True,
        is_refunded=False,
    )
    PaymentReceipt.objects.create(
        contract=contract1,
        client=client,
        amount=200,
        mode="ESPECES",
        payment_date=now().date(),
        next_due_date=None,
    )

    # Contrat 2 : partiellement payé avec remise
    contract2 = Contract.objects.create(
        client=client,
        created_by=user,
        service=service,
        amount_due=200,
        is_signed=False,
        is_refunded=False,
        discount_percent=10,
    )
    PaymentReceipt.objects.create(
        contract=contract2,
        client=client,
        amount=50,
        mode="VIREMENT",
        payment_date=now().date(),
        next_due_date=now().date() + timedelta(days=30),
    )

    # Contrat 3 : remboursé partiellement
    contract3 = Contract.objects.create(
        client=client,
        created_by=user,
        service=service,
        amount_due=300,
        is_signed=True,
        is_refunded=True,
        refund_amount=100,
    )
    PaymentReceipt.objects.create(
        contract=contract3,
        client=client,
        amount=150,
        mode="CB",
        payment_date=now().date(),
        next_due_date=None,
    )

    return [contract1, contract2, contract3]


def test_search_contracts_basic(auth_client, setup_contracts):
    url = reverse("contract-search")  # Assure-toi que le routeur a bien ce nom
    response = auth_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "items" in data
    assert "aggregates" in data
    assert data["total"] == 3
    assert data["aggregates"]["sum_amount_due"] == 700.0
    assert data["aggregates"]["count_signed"] == 2
    assert isinstance(data["items"], list)


def test_filter_signed_contracts(auth_client, setup_contracts):
    url = reverse("contract-search")
    response = auth_client.get(url, {"is_signed": "avec"})

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total"] == 2
    assert all(item["is_signed"] is True for item in data["items"])


def test_filter_with_discount(auth_client, setup_contracts):
    url = reverse("contract-search")
    response = auth_client.get(url, {"with_discount": "avec"})

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total"] == 1
    assert float(data["items"][0]["discount_percent"]) == 10.0


def test_filter_fully_paid(auth_client, setup_contracts):
    url = reverse("contract-search")
    response = auth_client.get(url, {"is_fully_paid": "avec"})

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total"] == 1
    assert float(data["items"][0]["amount_paid"]) == 200.0
    assert float(data["items"][0]["balance_due"]) == 0.0


def test_pagination_and_ordering(auth_client, setup_contracts):
    url = reverse("contract-search")
    response = auth_client.get(
        url, {"page": 1, "page_size": 2, "ordering": "-created_at"}
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data["items"]) <= 2
    assert data["page"] == 1
    assert data["page_size"] == 2
