import pytest
from django.contrib.auth import get_user_model

from api.comments.models import Comment
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
def test_str_representation(user, lead):
    comment = Comment.objects.create(lead=lead, author=user, content="Hello !")
    assert str(comment) == f"Commentaire #{comment.id} par {user.get_full_name()}"
