from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from api.clients.models import Client
from api.contracts.models import Contract
from api.lead_status.models import LeadStatus
from api.leads.constants import RDV_PLANIFIE
from api.leads.models import Lead
from api.services.models import Service
from api.users.models import User


@pytest.mark.django_db
class TestContractModel:
    def create_contract(self) -> Contract:
        lead_status = LeadStatus.objects.create(
            code=RDV_PLANIFIE, label="RDV planifié", color="gray"
        )
        lead = Lead.objects.create(
            first_name="John",
            last_name="Doe",
            phone="+33600000000",
            status=lead_status,
        )
        client = Client.objects.create(lead=lead)
        user = User.objects.create(
            email="test@tds.fr",
            first_name="Jean",
            last_name="Test",
            role="CONSEILLER",
            is_active=True,
        )
        service = Service.objects.create(
            code="TEST_SERVICE", label="Service A", price=Decimal("1000.00")
        )
        return Contract.objects.create(
            client=client,
            created_by=user,
            service=service,
            amount_due=Decimal("1000.00"),
        )

    def test_real_amount_is_discounted_correctly(self):
        contract = self.create_contract()
        contract.amount_due = Decimal("1000.00")
        contract.discount_percent = Decimal("20.00")
        contract.save()
        assert contract.real_amount == Decimal("800.00")

    def test_amount_paid_is_zero_when_no_receipts(self):
        contract = self.create_contract()
        assert contract.amount_paid == Decimal("0.00")

    def test_net_paid_subtracts_refund(self):
        from api.payments.models import PaymentReceipt

        contract = self.create_contract()
        PaymentReceipt.objects.create(
            client=contract.client,
            contract=contract,
            amount=Decimal("100.00"),
            mode="ESPECES",
            created_by=contract.created_by,
        )
        contract.refund_amount = Decimal("100.00")
        contract.save()
        assert contract.net_paid == Decimal("0.00")

    def test_balance_due_computed_correctly(self):
        contract = self.create_contract()
        contract.amount_due = Decimal("500.00")
        contract.discount_percent = Decimal("0.00")
        contract.save()
        assert contract.balance_due == Decimal("500.00")

    def test_contract_is_not_fully_paid_initially(self):
        contract = self.create_contract()
        contract.amount_due = Decimal("200.00")
        contract.save()
        assert not contract.is_fully_paid

    def test_negative_refund_amount_raises_validation_error(self):
        contract = self.create_contract()
        contract.refund_amount = Decimal("-50.00")
        with pytest.raises(ValidationError):
            contract.full_clean()

    def test_refund_cannot_exceed_amount_paid(self):
        from api.payments.models import PaymentReceipt

        contract = self.create_contract()
        PaymentReceipt.objects.create(
            client=contract.client,
            contract=contract,
            amount=Decimal("100.00"),
            mode="ESPECES",
            created_by=contract.created_by,
        )
        contract.refund_amount = Decimal("500.00")
        with pytest.raises(ValidationError):
            contract.full_clean()

    def test_apply_valid_refund_updates_fields(self):
        from api.payments.models import PaymentReceipt

        contract = self.create_contract()
        PaymentReceipt.objects.create(
            client=contract.client,
            contract=contract,
            amount=Decimal("150.00"),
            mode="ESPECES",
            created_by=contract.created_by,
        )
        contract.apply_refund(Decimal("100.00"))
        contract.refresh_from_db()
        assert contract.refund_amount == Decimal("100.00")
        assert contract.is_refunded is True

    def test_apply_negative_refund_raises_error(self):
        contract = self.create_contract()
        with pytest.raises(ValidationError):
            contract.apply_refund(Decimal("-10.00"))

    def test_string_representation(self):
        contract = self.create_contract()
        result = str(contract)
        assert result.startswith("Contrat")
