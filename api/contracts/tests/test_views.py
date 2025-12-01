from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from api.clients.models import Client
from api.contracts.models import Contract
from api.payments.models import PaymentReceipt
from api.services.models import Service
from api.users.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_user():
    return User.objects.create_user(
        email="admin@tds.fr",
        password="test",
        role="ADMIN",
        first_name="Admin",
        last_name="Test",
    )


@pytest.fixture
def auth_client(admin_user):
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client


@pytest.fixture
def client_with_lead():
    from api.leads.models import Lead, LeadStatus

    # Crée un statut valide
    status = LeadStatus.objects.create(code="NOUVEAU", label="Nouveau", color="#000000")
    lead = Lead.objects.create(
        first_name="Marc", last_name="Dupont", email="marc@example.com", status=status
    )
    return Client.objects.create(lead=lead)


@pytest.fixture
def contract(client_with_lead, admin_user):
    service = Service.objects.create(
        code="TEST_SERVICE", label="Test Service", price=Decimal("150.00")
    )
    return Contract.objects.create(
        client=client_with_lead,
        created_by=admin_user,
        service=service,
        amount_due=Decimal("150.00"),
        contract_url="https://example.com/fake.pdf",
    )


def test_send_email_contract_view(auth_client, contract, mocker):
    # Mock la tâche Celery
    mocked_task = mocker.patch("api.contracts.views.send_contract_email_task.delay")
    url = reverse("contract-send-email", kwargs={"pk": contract.id})
    res = auth_client.post(url)

    assert res.status_code == status.HTTP_202_ACCEPTED
    assert "va être envoyé" in res.data["detail"]
    mocked_task.assert_called_once_with(contract.id)


def test_get_receipts_empty(auth_client, contract):
    url = reverse("contract-receipts", kwargs={"pk": contract.id})
    res = auth_client.get(url)

    assert res.status_code == status.HTTP_200_OK
    assert isinstance(res.data, list)
    assert len(res.data) == 0


def test_refund_contract(auth_client, contract):
    from api.payments.models import PaymentReceipt

    # Préparer un contrat avec une URL S3 valide
    contract.refund_amount = Decimal("0.00")
    contract.contract_url = "https://s3.fr-par.scw.cloud/contracts/test_contract.pdf"
    contract.save()

    # Simuler un reçu
    PaymentReceipt.objects.create(
        contract=contract,
        client=contract.client,
        amount=Decimal("120.00"),
        receipt_url="https://s3.fr-par.scw.cloud/receipts/test_receipt.pdf",  # ← essentiel
    )

    url = reverse("contract-refund", kwargs={"pk": contract.id})
    payload = {"refund_amount": "50.00", "refund_note": "Client annulé"}
    res = auth_client.post(url, payload)

    assert res.status_code == status.HTTP_200_OK
    assert Decimal(res.data["refund_amount"]) == Decimal("50.00")
    assert res.data["is_refunded"] is True


def test_refund_contract_invalid_amount(auth_client, contract):
    url = reverse("contract-refund", kwargs={"pk": contract.id})
    res = auth_client.post(url, {"refund_amount": "-10.00"})

    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "supérieur à 0" in res.data["detail"]


def test_filter_contract_by_client(auth_client, contract):
    client_id = contract.client.id
    contract.contract_url = "https://s3.fr-par.scw.cloud/contracts/test_contract.pdf"
    contract.save()

    url = reverse("contract-list-by-client", kwargs={"client_id": client_id})
    res = auth_client.get(url)

    assert res.status_code == status.HTTP_200_OK
    assert len(res.data) == 1
    assert res.data[0]["id"] == contract.id
