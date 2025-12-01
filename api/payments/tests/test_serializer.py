from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from api.clients.models import Client
from api.contracts.models import Contract
from api.lead_status.models import LeadStatus
from api.leads.models import Lead
from api.payments.enums import PaymentMode
from api.payments.serializers import PaymentReceiptSerializer
from api.services.models import Service
from api.users.models import User, UserRoles

pytestmark = pytest.mark.django_db


@pytest.fixture
def sample_contract():
    status, _ = LeadStatus.objects.get_or_create(
        code="NOUVEAU", defaults={"label": "Nouveau", "color": "#000000"}
    )
    lead = Lead.objects.create(
        first_name="Alice", last_name="Martin", phone="+33600000001", status=status
    )
    client = Client.objects.create(lead=lead)
    service = Service.objects.create(
        code="VISA_LONG", label="Visa long séjour", price=Decimal("1200.00")
    )
    user = User.objects.create_user(
        email="admin@example.com",
        password="pass1234",
        role=UserRoles.ADMIN,
        first_name="Admin",
        last_name="User",
    )

    return Contract.objects.create(
        client=client,
        service=service,
        created_by=user,
        amount_due=Decimal("1200.00"),
    )


def test_valid_payment_receipt_serialization(sample_contract):
    receipt_data = {
        "client": sample_contract.client.pk,
        "contract": sample_contract.pk,
        "mode": PaymentMode.CB,
        "payment_date": datetime.now().isoformat(),
        "amount": "600.00",
        "next_due_date": (datetime.now() + timedelta(days=30)).date().isoformat(),
    }

    serializer = PaymentReceiptSerializer(data=receipt_data)
    assert serializer.is_valid(), serializer.errors
    instance = serializer.save()

    assert instance.client == sample_contract.client
    assert instance.contract == sample_contract
    assert instance.mode == PaymentMode.CB
    assert instance.amount == Decimal("600.00")
    assert instance.receipt_url is None  # car non généré


@pytest.mark.parametrize("invalid_amount", ["0.00", "-10.00"])
def test_invalid_amount_raises_error(sample_contract, invalid_amount):
    data = {
        "client": sample_contract.client.pk,
        "contract": sample_contract.pk,
        "mode": PaymentMode.VIREMENT,
        "payment_date": datetime.now().isoformat(),
        "amount": invalid_amount,
    }
    serializer = PaymentReceiptSerializer(data=data)
    assert not serializer.is_valid()
    assert "amount" in serializer.errors
    assert "supérieur à zéro" in str(serializer.errors["amount"][0])


def test_invalid_payment_mode(sample_contract):
    data = {
        "client": sample_contract.client.pk,
        "contract": sample_contract.pk,
        "mode": "EN_NATURE",  # mode invalide
        "payment_date": datetime.now().isoformat(),
        "amount": "100.00",
    }
    serializer = PaymentReceiptSerializer(data=data)
    assert not serializer.is_valid()
    assert "mode" in serializer.errors
    assert "n'est pas un choix valide" in str(serializer.errors["mode"][0])
