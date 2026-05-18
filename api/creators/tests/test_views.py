import pytest
from rest_framework import status
from api.creators.models import CreatorProfile, SocialAccountLead
from api.users.roles import UserRoles

pytestmark = pytest.mark.django_db

# ─────────────────────────────────────────────────────────────────────────────
# PERMISSIONS
# ─────────────────────────────────────────────────────────────────────────────

def test_access_denied_if_not_authenticated(api_client):
    response = api_client.get("/api/creators/")
    assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

def test_access_denied_if_not_staff_or_admin(api_client, creator_user):
    api_client.force_authenticate(user=creator_user)
    response = api_client.get("/api/creators/")
    assert response.status_code == status.HTTP_403_FORBIDDEN

def test_access_allowed_if_admin(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)
    response = api_client.get("/api/creators/")
    assert response.status_code == status.HTTP_200_OK

# ─────────────────────────────────────────────────────────────────────────────
# CREATOR PROFILE
# ─────────────────────────────────────────────────────────────────────────────

def test_create_creator_via_api(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)
    data = {
        "email": "new_api_creator@test.com",
        "first_name": "API",
        "last_name": "Creator",
        "password": "password123",
        "promo_code": "APICODE",
        "commission_rate": 10.0
    }
    response = api_client.post("/api/creators/", data=data)
    assert response.status_code == status.HTTP_201_CREATED
    assert CreatorProfile.objects.filter(promo_code="APICODE").exists()
    assert CreatorProfile.objects.get(promo_code="APICODE").user.role == UserRoles.CREATOR

def test_list_creators_with_pagination(api_client, admin_user, creator_profile):
    api_client.force_authenticate(user=admin_user)
    response = api_client.get("/api/creators/")
    assert response.status_code == status.HTTP_200_OK
    assert "results" in response.data
    assert "total_pages" in response.data
    assert response.data["count"] >= 1

def test_creator_stats(api_client, admin_user, creator_profile):
    api_client.force_authenticate(user=admin_user)
    response = api_client.get("/api/creators/stats/")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["total"] >= 1
    assert "active" in response.data

# ─────────────────────────────────────────────────────────────────────────────
# SOCIAL ACCOUNT LEAD
# ─────────────────────────────────────────────────────────────────────────────

def test_list_social_leads_filters(api_client, admin_user, social_lead):
    api_client.force_authenticate(user=admin_user)
    
    # Filter by platform
    response = api_client.get(f"/api/social-leads/?platform={social_lead.platform}")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) >= 1
    
    # Search by username
    response = api_client.get(f"/api/social-leads/?search={social_lead.username}")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["results"][0]["username"] == social_lead.username

def test_social_lead_custom_actions(api_client, admin_user, social_lead):
    api_client.force_authenticate(user=admin_user)
    
    # mark-contacted
    response = api_client.post(f"/api/social-leads/{social_lead.id}/mark_contacted/")
    assert response.status_code == status.HTTP_200_OK
    social_lead.refresh_from_db()
    assert social_lead.contact_status == SocialAccountLead.ContactStatus.CONTACTED

    # mark-positive
    response = api_client.post(f"/api/social-leads/{social_lead.id}/mark_positive/")
    assert response.status_code == status.HTTP_200_OK
    social_lead.refresh_from_db()
    assert social_lead.contact_status == SocialAccountLead.ContactStatus.POSITIVE

def test_link_creator_action(api_client, admin_user, social_lead, creator_profile):
    api_client.force_authenticate(user=admin_user)
    # Clear existing creator link if any (from fixture)
    social_lead.creator = None
    social_lead.contact_status = SocialAccountLead.ContactStatus.NEW
    social_lead.save()

    data = {"creator_id": str(creator_profile.id)}
    response = api_client.post(f"/api/social-leads/{social_lead.id}/link_creator/", data=data)
    
    assert response.status_code == status.HTTP_200_OK
    social_lead.refresh_from_db()
    assert social_lead.creator == creator_profile
    assert social_lead.contact_status == SocialAccountLead.ContactStatus.CONVERTED

def test_social_leads_stats(api_client, admin_user, social_lead):
    api_client.force_authenticate(user=admin_user)
    response = api_client.get("/api/social-leads/stats/")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["total"] >= 1
    assert "viable" in response.data
    assert "converted" in response.data
