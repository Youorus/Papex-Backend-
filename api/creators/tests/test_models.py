import pytest
from django.db import IntegrityError
from api.creators.models import CreatorProfile, SocialAccountLead
from api.users.roles import UserRoles

pytestmark = pytest.mark.django_db

def test_creator_profile_creation(creator_user):
    profile = CreatorProfile.objects.create(
        user=creator_user,
        promo_code="WELCOME2026",
        status=CreatorProfile.Status.ACTIVE
    )
    assert profile.user == creator_user
    assert profile.promo_code == "WELCOME2026"
    assert profile.status == CreatorProfile.Status.ACTIVE
    assert str(profile) == f"{creator_user.get_full_name()} (WELCOME2026)"

def test_creator_profile_unique_promo_code(creator_user, admin_user):
    CreatorProfile.objects.create(user=creator_user, promo_code="UNIQUE")
    with pytest.raises(IntegrityError):
        CreatorProfile.objects.create(user=admin_user, promo_code="UNIQUE")

def test_social_account_lead_creation():
    lead = SocialAccountLead.objects.create(
        platform=SocialAccountLead.Platform.INSTAGRAM,
        username="insta_user",
        followers_count=1000,
        is_viable=True
    )
    assert lead.platform == SocialAccountLead.Platform.INSTAGRAM
    assert lead.username == "insta_user"
    assert lead.contact_status == SocialAccountLead.ContactStatus.NEW
    assert str(lead) == "insta_user on Instagram"

def test_social_account_lead_unique_platform_username():
    SocialAccountLead.objects.create(
        platform=SocialAccountLead.Platform.YOUTUBE,
        username="youtuber"
    )
    with pytest.raises(IntegrityError):
        SocialAccountLead.objects.create(
            platform=SocialAccountLead.Platform.YOUTUBE,
            username="youtuber"
        )

def test_social_account_lead_link_to_creator(creator_profile):
    lead = SocialAccountLead.objects.create(
        platform=SocialAccountLead.Platform.FACEBOOK,
        username="fb_user",
        creator=creator_profile
    )
    assert lead.creator == creator_profile
    assert creator_profile.social_leads.count() == 1
