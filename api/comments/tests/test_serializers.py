import pytest
from django.contrib.auth import get_user_model

from api.comments.models import Comment
from api.comments.serializers import CommentSerializer
from api.lead_status.models import LeadStatus
from api.leads.models import Lead

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="test@test.com", first_name="Test", last_name="User", password="password"
    )


@pytest.fixture
def lead_status(db):
    return LeadStatus.objects.create(code="NOUVEAU", label="Nouveau")


@pytest.fixture
def lead(db, lead_status):
    return Lead.objects.create(
        first_name="Marc", last_name="Nkue", status=lead_status, phone="+33612345678"
    )


@pytest.mark.django_db
class TestCommentSerializer:
    def test_valid_data(self, lead, user):
        data = {"lead_id": lead.id, "content": "Ceci est un commentaire valide"}
        request = type("Request", (), {"user": user, "auth": True})()
        serializer = CommentSerializer(data=data, context={"request": request})
        assert serializer.is_valid()

    def test_content_too_short(self, lead, user):
        data = {"lead_id": lead.id, "content": "a"}
        request = type("Request", (), {"user": user, "auth": True})()
        serializer = CommentSerializer(data=data, context={"request": request})
        assert not serializer.is_valid()

    def test_content_too_long(self, lead, user):
        data = {"lead_id": lead.id, "content": "a" * 3000}
        request = type("Request", (), {"user": user, "auth": True})()
        serializer = CommentSerializer(data=data, context={"request": request})
        assert not serializer.is_valid()

    def test_lead_id_invalid(self, user):
        data = {"lead_id": 9999, "content": "Test"}
        request = type("Request", (), {"user": user, "auth": True})()
        serializer = CommentSerializer(data=data, context={"request": request})
        assert not serializer.is_valid()

    def test_create_requires_auth(self, lead):
        data = {"lead_id": lead.id, "content": "Commentaire"}
        # On simule un request sans utilisateur authentifié
        request = type("Request", (), {"user": None, "auth": False})()
        serializer = CommentSerializer(data=data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        import pytest

        with pytest.raises(Exception):
            serializer.save()
