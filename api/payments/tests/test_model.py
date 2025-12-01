from decimal import Decimal

import pytest
from django.utils import timezone

from api.clients.models import Client
from api.contracts.models import Contract
from api.lead_status.models import LeadStatus
from api.leads.constants import RDV_PLANIFIE
from api.leads.models import Lead
from api.payments.enums import PaymentMode
from api.payments.models import PaymentReceipt
from api.services.models import Service
from api.users.models import User


@pytest.mark.django_db
def test_create_payment_receipt():
    lead_status = LeadStatus.objects.create(
        code=RDV_PLANIFIE, label="RDV planifié", color="gray"
    )
    lead = Lead.objects.create(
        first_name="Marc", last_name="Test", phone="+33600000000", status=lead_status
    )
    client = Client.objects.create(lead=lead)

    user = User.objects.create_user(
        email="test@example.com",
        password="password",
        first_name="Jean",
        last_name="Dupont",
        role="ADMIN",
    )

    service = Service.objects.create(
        code="VISA_LONG", label="Visa long s\u00e9jour", price=Decimal("1000.00")
    )

    contract = Contract.objects.create(
        client=client,
        service=service,
        amount_due=Decimal("1000.00"),
        discount_percent=Decimal("0.00"),
        created_by=user,
    )

    receipt = PaymentReceipt.objects.create(
        client=client,
        contract=contract,
        amount=Decimal("500.00"),
        mode=PaymentMode.VIREMENT.value,
        payment_date=timezone.now(),
        created_by=user,
    )

    assert receipt.pk is not None
    assert receipt.amount == Decimal("500.00")
    assert receipt.mode == PaymentMode.VIREMENT
    assert receipt.contract == contract
    assert receipt.client == client
    assert receipt.created_by == user


@pytest.mark.django_db
def test_receipt_str_method():
    status, _ = LeadStatus.objects.get_or_create(
        code="NOUVEAU", defaults={"label": "Nouveau", "color": "#000000"}
    )
    lead = Lead.objects.create(
        first_name="Marc", last_name="Test", phone="+33600000000", status=status
    )
    client = Client.objects.create(lead=lead)

    receipt = PaymentReceipt.objects.create(
        client=client, amount=Decimal("200.00"), mode=PaymentMode.ESPECES.value
    )

    assert str(receipt).startswith("Re\u00e7u 200.00 \u20ac -")


@pytest.mark.django_db
def test_generate_pdf_mocked(monkeypatch):
    status, _ = LeadStatus.objects.get_or_create(
        code="NOUVEAU", defaults={"label": "Nouveau", "color": "#000000"}
    )
    lead = Lead.objects.create(
        first_name="Marc", last_name="Test", phone="+33600000000", status=status
    )
    client = Client.objects.create(lead=lead)

    receipt = PaymentReceipt.objects.create(
        client=client, amount=Decimal("150.00"), mode=PaymentMode.CHEQUE.value
    )

    monkeypatch.setattr(
        "api.payments.models.generate_receipt_pdf", lambda r: b"PDFDATA"
    )
    monkeypatch.setattr(
        "api.payments.models.store_receipt_pdf",
        lambda r, b: "https://fakeurl.com/receipt.pdf",
    )

    receipt.generate_pdf()
    receipt.refresh_from_db()
    assert receipt.receipt_url == "https://fakeurl.com/receipt.pdf"
