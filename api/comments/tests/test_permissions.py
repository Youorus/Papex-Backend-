import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework.test import APIRequestFactory

from api.comments.models import Comment
from api.comments.permissions import IsCommentAuthorOrAdmin
from api.lead_status.models import LeadStatus
from api.leads.models import Lead

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="test1@test.com",
        first_name="Jean",
        last_name="Dupont",
        password="pass123",
    )


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        email="admin@test.com",
        first_name="Admin",
        last_name="User",
        password="adminpass",
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
def comment(db, lead, user):
    return Comment.objects.create(lead=lead, author=user, content="Test comment")


@pytest.mark.django_db
class TestIsCommentAuthorOrAdmin:
    def test_author_permission(self, user, comment):
        perm = IsCommentAuthorOrAdmin()
        request = APIRequestFactory().get("/")
        request.user = user
        assert perm.has_object_permission(request, None, comment)

    def test_admin_permission(self, admin_user, comment):
        perm = IsCommentAuthorOrAdmin()
        request = APIRequestFactory().get("/")
        request.user = admin_user
        assert perm.has_object_permission(request, None, comment)

    def test_other_user_no_permission(self, other_user, comment):
        perm = IsCommentAuthorOrAdmin()
        request = APIRequestFactory().get("/")
        request.user = other_user
        assert not perm.has_object_permission(request, None, comment)

    def test_anonymous_no_permission(self, comment):
        perm = IsCommentAuthorOrAdmin()
        request = APIRequestFactory().get("/")
        request.user = AnonymousUser()
        assert not perm.has_object_permission(request, None, comment)
