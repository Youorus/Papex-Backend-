import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from api.comments.models import Comment
from api.lead_status.models import LeadStatus
from api.leads.models import Lead

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="user@test.com", first_name="Jean", last_name="Dupont", password="pass123"
    )


@pytest.fixture
def other_user(db):
    return User.objects.create_user(
        email="other@test.com",
        first_name="Paul",
        last_name="Martin",
        password="pass456",
    )


@pytest.fixture
def lead_status(db):
    return LeadStatus.objects.create(code="NOUVEAU", label="Nouveau")


@pytest.fixture
def lead(db, lead_status):
    return Lead.objects.create(
        first_name="Marc", last_name="Nkue", status=lead_status, phone="+33612345678"
    )


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
class TestCommentAPI:
    def test_list_comments_by_lead(self, api_client, lead, user):
        comment = Comment.objects.create(
            lead=lead, author=user, content="Commentaire test"
        )
        url = reverse("comments-by-lead", kwargs={"lead_id": lead.id})
        api_client.force_authenticate(user=user)
        resp = api_client.get(url)
        assert resp.status_code == 200
        assert len(resp.data) == 1

    def test_create_comment_unauthenticated(self, api_client, lead):
        url = reverse("comments-list")
        data = {"lead_id": lead.id, "content": "Commentaire non authentifié"}
        resp = api_client.post(url, data, format="json")
        assert resp.status_code == 401

    def test_create_comment_authenticated(self, api_client, lead, user):
        api_client.force_authenticate(user=user)
        url = reverse("comments-list")
        data = {"lead_id": lead.id, "content": "Commentaire authentifié"}
        resp = api_client.post(url, data, format="json")
        assert resp.status_code == 201
        assert resp.data["content"] == "Commentaire authentifié"

    def test_update_comment_by_author(self, api_client, lead, user):
        api_client.force_authenticate(user=user)
        comment = Comment.objects.create(
            lead=lead, author=user, content="Ancien contenu"
        )
        url = reverse("comments-detail", args=[comment.id])
        resp = api_client.patch(url, {"content": "Nouveau contenu"}, format="json")
        assert resp.status_code == 200
        assert resp.data["content"] == "Nouveau contenu"

    def test_update_comment_by_other_user(self, api_client, lead, user, other_user):
        comment = Comment.objects.create(
            lead=lead, author=user, content="Contenu initial"
        )
        api_client.force_authenticate(user=other_user)
        url = reverse("comments-detail", args=[comment.id])
        resp = api_client.patch(url, {"content": "Modif par un autre"}, format="json")
        assert resp.status_code == 403
