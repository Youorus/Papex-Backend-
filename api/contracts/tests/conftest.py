from decimal import Decimal

import pytest

from api.clients.models import Client
from api.contracts.models import Contract
from api.leads.models import Lead
from api.services.models import Service
from api.users.models import User


@pytest.fixture
def contract(db):
    lead = Lead.objects.create(first_name="Test", last_name="Client")
    client = Client.objects.create(lead=lead)
    user = User.objects.create(email="test@tds.fr")
    service = Service.objects.create(name="Service A", amount=Decimal("1000.00"))
    return Contract.objects.create(
        client=client,
        created_by=user,
        service=service,
        amount_due=Decimal("1000.00"),
    )
