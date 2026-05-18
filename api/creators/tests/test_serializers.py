import pytest
from django.contrib.auth import get_user_model
from api.creators.serializers import (
    CreatorProfileCreateSerializer,
    CreatorProfileSerializer,
    SocialAccountLeadSerializer
)
from api.users.roles import UserRoles

User = get_user_model()
pytestmark = pytest.mark.django_db

def test_creator_profile_create_serializer():
    data = {
        "email": "new_creator@test.com",
        "first_name": "New",
        "last_name": "Creator",
        "password": "securepassword",
        "promo_code": "NEWCODE20",
        "commission_rate": 12.50
    }
    serializer = CreatorProfileCreateSerializer(data=data)
    assert serializer.is_valid()
    profile = serializer.save()
    
    assert profile.user.email == "new_creator@test.com"
    assert profile.user.role == UserRoles.CREATOR
    assert profile.promo_code == "NEWCODE20"
    assert profile.commission_rate == 12.50

def test_creator_profile_serializer(creator_profile):
    serializer = CreatorProfileSerializer(instance=creator_profile)
    data = serializer.data
    assert data["email"] == creator_profile.user.email
    assert data["promo_code"] == creator_profile.promo_code
    assert data["full_name"] == creator_profile.user.get_full_name()

def test_social_account_lead_serializer(social_lead):
    serializer = SocialAccountLeadSerializer(instance=social_lead)
    data = serializer.data
    assert data["username"] == social_lead.username
    assert data["platform"] == social_lead.platform
    assert str(data["creator"]["id"]) == str(social_lead.creator.id)
    assert data["creator"]["promo_code"] == social_lead.creator.promo_code
