import pytest
from unittest.mock import patch

from api.clients.models import Client
from api.documents.models import Document
from api.documents.serializers import DocumentSerializer
from api.lead_status.models import LeadStatus
from api.leads.models import Lead


@pytest.mark.django_db
class TestDocumentSerializer:
    @pytest.fixture
    def client(self):
        status = LeadStatus.objects.create(
            code="NOUVEAU", label="Nouveau", color="#C1E8FF"
        )
        lead = Lead.objects.create(first_name="Marc", last_name="Nkue", status=status)
        return Client.objects.create(lead=lead)

    @patch("api.documents.serializers.generate_presigned_url")
    def test_serializer_output(self, mock_generate_url, client):
        mock_generate_url.return_value = "https://s3.fr-par.scw.cloud/documents-clients/marc_nkue/mon_fichier.pdf?X-Amz-Signature=abc123"
        doc = Document.objects.create(client=client, url="https://s3.fr-par.scw.cloud/documents-clients/marc_nkue/mon_fichier.pdf")
        data = DocumentSerializer(doc).data
        assert data["client"] == client.id
        assert "mon_fichier.pdf" in data["url"]
        assert "X-Amz-Signature" in data["url"]
        assert "uploaded_at" in data

    def test_serializer_readonly_fields(self, client):
        doc = Document.objects.create(client=client, url="https://s3.fr-par.scw.cloud/documents-clients/marc_nkue/mon_fichier.pdf")
        serializer = DocumentSerializer(doc)
        assert serializer.fields["id"].read_only
        assert serializer.fields["uploaded_at"].read_only
        assert serializer.fields["url"].read_only
