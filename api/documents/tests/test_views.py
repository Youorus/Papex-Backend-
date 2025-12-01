import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from api.clients.models import Client
from api.documents.models import Document
from api.lead_status.models import LeadStatus
from api.leads.models import Lead
from api.users.models import User


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="test@user.com",
        first_name="Marc",
        last_name="Nkue",
        password="pwd",
        role="ADMIN",
    )


@pytest.fixture
def client(user):
    status = LeadStatus.objects.create(code="NOUVEAU", label="Nouveau", color="#C1E8FF")
    lead = Lead.objects.create(first_name="Marc", last_name="Nkue", status=status)
    return Client.objects.create(lead=lead)


@pytest.mark.django_db
class TestDocumentAPI:
    def test_upload_single_document(self, client, user, monkeypatch):
        api_client = APIClient()
        api_client.force_authenticate(user=user)
        url = reverse("document-list")
        # Mock du stockage cloud pour retourner une URL factice
        monkeypatch.setattr(
            "api.documents.views.store_client_document",
            lambda client, file, name: "https://s3.fr-par.scw.cloud/documents/mock.pdf",
        )
        from io import BytesIO

        file = BytesIO(b"dummy content")
        file.name = "file.pdf"
        resp = api_client.post(
            url + f"?client={client.id}", {"file": file}, format="multipart"
        )
        assert resp.status_code == 201
        assert Document.objects.filter(client=client).count() == 1

    def test_upload_multi_files(self, client, user, monkeypatch):
        api_client = APIClient()
        api_client.force_authenticate(user=user)
        url = reverse("document-list")
        monkeypatch.setattr(
            "api.documents.views.store_client_document",
            lambda client, file, name: "https://s3.fr-par.scw.cloud/documents/mock.pdf",
        )
        from io import BytesIO

        file1 = BytesIO(b"doc1")
        file1.name = "doc1.pdf"
        file2 = BytesIO(b"doc2")
        file2.name = "doc2.pdf"
        resp = api_client.post(
            url + f"?client={client.id}", {"files": [file1, file2]}, format="multipart"
        )
        assert resp.status_code == 201
        assert Document.objects.filter(client=client).count() == 2

    def test_list_documents(self, client, user):
        api_client = APIClient()
        api_client.force_authenticate(user=user)
        url = reverse("document-list")
        Document.objects.filter(client=client).delete()
        Document.objects.create(client=client, url="https://s3.fr-par.scw.cloud/documents/doc1.pdf")
        Document.objects.create(client=client, url="https://s3.fr-par.scw.cloud/documents/doc2.pdf")
        resp = api_client.get(url + f"?client={client.id}")
        assert resp.status_code == 200
        assert len(resp.data["results"]) == 2

    def test_delete_document(self, client, user, monkeypatch):
        api_client = APIClient()
        api_client.force_authenticate(user=user)
        doc = Document.objects.create(
            client=client, url="https://s3.fr-par.scw.cloud/documents/todelete.pdf"
        )
        url = reverse("document-detail", args=[doc.id])
        monkeypatch.setattr(
            "api.storage_backends.MinioDocumentStorage.delete", lambda self, path: None
        )
        resp = api_client.delete(url)
        assert resp.status_code == 204
        assert not Document.objects.filter(pk=doc.id).exists()

    def test_permission_required(self, client):
        api_client = APIClient()
        doc = Document.objects.create(
            client=client, url="https://s3.fr-par.scw.cloud/documents/protected.pdf"
        )
        url = reverse("document-detail", args=[doc.id])
        resp = api_client.delete(url)
        assert resp.status_code in [401, 403]
