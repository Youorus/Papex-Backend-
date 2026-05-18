import pytest
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from api.creators.models import CreatorProfile, SocialAccountLead
from api.users.roles import UserRoles

User = get_user_model()

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def admin_user():
    return User.objects.create_user(
        email="admin@test.com",
        password="password123",
        role=UserRoles.ADMIN,
        first_name="Admin",
        last_name="Test"
    )

@pytest.fixture
def creator_user():
    return User.objects.create_user(
        email="creator@test.com",
        password="password123",
        role=UserRoles.CREATOR,
        first_name="Creator",
        last_name="Test"
    )

@pytest.fixture
def creator_profile(creator_user):
    return CreatorProfile.objects.create(
        user=creator_user,
        promo_code="PROMO10",
        commission_rate=15.00
    )

@pytest.fixture
def social_lead(creator_profile):
    return SocialAccountLead.objects.create(
        platform=SocialAccountLead.Platform.TIKTOK,
        username="tiktok_star",
        followers_count=5000,
        is_viable=True,
        creator=creator_profile
    )
