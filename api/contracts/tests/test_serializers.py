from decimal import Decimal
from urllib.parse import urlparse, unquote
from unittest.mock import patch

import pytest
from django.utils import timezone

from api.clients.models import Client
from api.contracts.models import Contract
from api.contracts.serializer import ContractSerializer
from api.services.models import Service
from api.users.models import User
from api.utils.cloud.scw.bucket_utils import generate_presigned_url

"""
Vérifie que le serializer `ContractSerializer` retourne les valeurs calculées correctement :
- Montant dû réel après remise
- Montant payé, net payé et solde dû
- Statut de paiement
"""


@pytest.mark.django_db
@patch("api.contracts.serializer.generate_presigned_url")
def test_contract_serializer_values(mock_generate_url):
    """
    Vérifie que le serializer `ContractSerializer` retourne les bonnes valeurs :
    - Montant dû réel après remise
    - Montant payé, net payé et solde dû
    - Statut de paiement
    - URL contract brute si externe
    """
    mock_generate_url.return_value = (
        "https://s3.fr-par.scw.cloud/contracts/contrat-test.pdf?X-Amz-Signature=fake"
    )

    from api.lead_status.models import LeadStatus
    from api.leads.models import Lead

    status, _ = LeadStatus.objects.get_or_create(
        code="NOUVEAU", defaults={"label": "Nouveau", "color": "#000000"}
    )

    lead = Lead.objects.create(
        first_name="Marc", last_name="Dupont", phone="+33600000000", status=status
    )

    client = Client.objects.create(lead=lead)

    service = Service.objects.create(
        code="VISA_LONG",
        label="Visa long séjour",
        price=Decimal("1000.00")
    )

    user = User.objects.create_user(
        email="test@example.com",
        first_name="Admin",
        last_name="User",
        password="securepassword123",
        role="ADMIN",
    )

    contract = Contract.objects.create(
        client=client,
        service=service,
        created_by=user,
        amount_due=Decimal("1000.00"),
        discount_percent=Decimal("20.00"),
        refund_amount=Decimal("100.00"),
        contract_url="https://s3.fr-par.scw.cloud/contracts/contrat-test.pdf",
        is_signed=True,
        created_at=timezone.now(),
    )

    contract.receipts.create(amount=Decimal("500.00"), client=client)

    serializer = ContractSerializer(contract)
    data = serializer.data

    real_amount_due = Decimal("800.00")           # 1000 * 0.80
    amount_paid = Decimal("500.00")               # reçu
    net_paid = Decimal("400.00")                  # 500 - 100
    balance_due = Decimal("400.00")               # 800 - 400

    assert Decimal(data["amount_due"]) == Decimal("1000.00")
    assert Decimal(data["discount_percent"]) == Decimal("20.00")
    assert Decimal(data["real_amount_due"]) == real_amount_due
    assert Decimal(data["amount_paid"]) == amount_paid
    assert Decimal(data["net_paid"]) == net_paid
    assert Decimal(data["balance_due"]) == balance_due
    assert data["is_fully_paid"] is False, f"Expected is_fully_paid to be False, but got {data['is_fully_paid']}"
    assert data["contract_url"].startswith("https://s3.fr-par.scw.cloud/contracts/")
    assert "contrat-test.pdf" in data["contract_url"]
    assert "X-Amz-Signature" in data["contract_url"]
    assert data["client"] == contract.client.id
    assert data["service"] == contract.service.id
    assert data["is_signed"] is True

def get_contract_url(self, obj):
    if obj.contract_url:
        parsed = urlparse(obj.contract_url)
        if "s3." in parsed.netloc:  # URL interne Scaleway ⇒ signer
            path = unquote(parsed.path)
            key = "/".join(path.strip("/").split("/")[1:])  # Retire le préfixe (ex: "contracts/")
            return generate_presigned_url("contracts", key)
        return obj.contract_url  # URL externe ⇒ retourne telle quelle
    return None