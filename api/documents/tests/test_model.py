import pytest

from api.clients.models import Client
from api.documents.models import Document
from api.lead_status.models import LeadStatus
from api.leads.models import Lead


@pytest.mark.django_db
class TestDocumentModel:
    @pytest.fixture
    def client(self):
        # On crée tout l’arbre de dépendance !
        status = LeadStatus.objects.create(
            code="NOUVEAU", label="Nouveau", color="#C1E8FF"
        )
        lead = Lead.objects.create(first_name="Marc", last_name="Nkue", status=status)
        return Client.objects.create(lead=lead)

    def test_create_document(self, client):
        doc = Document.objects.create(client=client, url="https://cloud.test/doc.pdf")
        assert doc.pk is not None
        assert doc.url == "https://cloud.test/doc.pdf"

    def test_str_representation(self, client):
        doc = Document.objects.create(client=client, url="https://cloud.test/doc.pdf")
        assert str(doc).startswith(str(client))
