from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from api.clients.models import Client
from api.contracts.models import Contract
from api.lead_status.models import LeadStatus
from api.leads.constants import RDV_PLANIFIE
from api.leads.models import Lead
from api.payments.models import PaymentReceipt
from api.services.models import Service
from api.statut_dossier.models import StatutDossier
from api.users.models import User, UserRoles


@pytest.mark.django_db
class TestPaymentReceiptViewSet:
    @pytest.fixture
    def admin_user(self):
        return User.objects.create_user(
            email="admin@tds.fr",
            password="pass",
            role=UserRoles.ADMIN,
            first_name="Admin",
            last_name="User",
        )

    @pytest.fixture
    def client_and_lead(self):
        lead_status = LeadStatus.objects.create(
            code=RDV_PLANIFIE, label="RDV planifié", color="gray"
        )
        lead = Lead.objects.create(
            first_name="Marc",
            last_name="Test",
            email="marc@example.com",
            phone="+33600000000",
            status=lead_status,
        )
        lead.save()
        client = Client.objects.create(lead=lead)
        return client, lead

    @pytest.fixture
    def contract(self, client_and_lead):
        client, _ = client_and_lead
        service = Service.objects.create(
            code="TEST_SERVICE", label="Service A", price=Decimal("1000.00")
        )
        return Contract.objects.create(
            client=client, service=service, amount_due=Decimal("1000.00")
        )

    @pytest.fixture
    def receipt(self, client_and_lead, contract, admin_user):
        client, _ = client_and_lead
        return PaymentReceipt.objects.create(
            client=client,
            contract=contract,
            amount=Decimal("100.00"),
            mode="CARTE",
            created_by=admin_user,
            receipt_url="https://dummy.url/receipt.pdf",
        )

    @pytest.fixture
    def api_client(self, admin_user):
        client = APIClient()
        client.force_authenticate(user=admin_user)
        return client

    def test_send_receipts_email_success(self, api_client, client_and_lead, receipt):
        client, lead = client_and_lead
        url = reverse("receipts-send-receipts-email")
        data = {
            "lead_id": lead.id,
            "receipt_ids": [receipt.id],
        }
        response = api_client.post(url, data=data, format="json")
        assert response.status_code == 200
        assert "Envoi des reçus programmé" in response.data["detail"]

    def test_send_receipts_email_missing_fields(self, api_client):
        url = reverse("receipts-send-receipts-email")
        response = api_client.post(url, data={}, format="json")
        assert response.status_code == 400
        assert "lead_id et receipt_ids sont requis." in response.data["detail"]

    def test_send_receipts_email_invalid_lead(self, api_client, receipt):
        url = reverse("receipts-send-receipts-email")
        data = {"lead_id": 9999, "receipt_ids": [receipt.id]}
        response = api_client.post(url, data=data, format="json")
        assert response.status_code == 404
        assert "Lead introuvable" in response.data["detail"]

    def test_send_receipts_email_invalid_receipt_ids(self, api_client, client_and_lead):
        _, lead = client_and_lead
        url = reverse("receipts-send-receipts-email")
        data = {"lead_id": lead.id, "receipt_ids": ["abc"]}
        response = api_client.post(url, data=data, format="json")
        assert response.status_code == 400
        assert "receipt_ids doit contenir des entiers" in response.data["detail"]
