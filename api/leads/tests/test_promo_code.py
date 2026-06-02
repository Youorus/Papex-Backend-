import pytest
from rest_framework import status
from rest_framework.test import APIClient
from api.leads.models import Lead
from api.creators.models import CreatorProfile, PromoCode
from api.users.models import User

# Mark all tests in this file as Django tests
pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def test_user(django_user_model):
    return django_user_model.objects.create_user(
        email="testuser@test.com",
        password="password",
        first_name="Test",
        last_name="User",
        role="ADMIN",
    )


@pytest.fixture
def test_creator(django_user_model):
    creator_user = django_user_model.objects.create_user(
        email="creator@test.com",
        password="password",
        first_name="Creator",
        last_name="Test",
    )
    return CreatorProfile.objects.create(user=creator_user, status=CreatorProfile.Status.ACTIVE)


@pytest.fixture
def active_promo_code(test_creator):
    return PromoCode.objects.create(
        creator=test_creator, code="PROMO1", status=PromoCode.Status.ACTIVE
    )


@pytest.fixture
def inactive_promo_code(test_creator):
    return PromoCode.objects.create(
        creator=test_creator, code="PROMO2", status=PromoCode.Status.INACTIVE
    )


@pytest.fixture
def sample_lead(lead_status):
    return Lead.objects.create(
        first_name="John", last_name="Doe", phone="1234567890", status=lead_status
    )


def test_associate_promo_code_success(api_client, test_user, sample_lead, active_promo_code):
    api_client.force_authenticate(user=test_user)
    url = f"/api/leads/{sample_lead.id}/promo-code/"
    data = {"code": "PROMO1"}

    response = api_client.put(url, data, format="json")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["success"] == "Promo code associated."
    assert response.data["promo_code_details"]["code"] == "PROMO1"
    assert response.data["promo_code_details"]["creator_email"] == "creator@test.com"

    sample_lead.refresh_from_db()
    assert sample_lead.promo_code == active_promo_code
    assert sample_lead.creator_profile == active_promo_code.creator


def test_associate_inactive_promo_code_fails(api_client, test_user, sample_lead, inactive_promo_code):
    api_client.force_authenticate(user=test_user)
    url = f"/api/leads/{sample_lead.id}/promo-code/"
    data = {"code": "PROMO2"}

    response = api_client.put(url, data, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["error"] == "Invalid or inactive promo code."

    sample_lead.refresh_from_db()
    assert sample_lead.promo_code is None


def test_associate_nonexistent_promo_code_fails(api_client, test_user, sample_lead):
    api_client.force_authenticate(user=test_user)
    url = f"/api/leads/{sample_lead.id}/promo-code/"
    data = {"code": "FAKECODE"}

    response = api_client.put(url, data, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["error"] == "Invalid or inactive promo code."


def test_delete_promo_code_association_success(api_client, test_user, sample_lead, active_promo_code):
    # First, associate the code
    sample_lead.promo_code = active_promo_code
    sample_lead.creator_profile = active_promo_code.creator
    sample_lead.save()
    assert sample_lead.promo_code is not None

    # Now, test deletion
    api_client.force_authenticate(user=test_user)
    url = f"/api/leads/{sample_lead.id}/promo-code/"
    response = api_client.delete(url)

    assert response.status_code == status.HTTP_204_NO_CONTENT

    sample_lead.refresh_from_db()
    assert sample_lead.promo_code is None
    assert sample_lead.creator_profile is None


def test_get_lead_with_promo_code_details(api_client, test_user, sample_lead, active_promo_code):
    sample_lead.promo_code = active_promo_code
    sample_lead.creator_profile = active_promo_code.creator
    sample_lead.save()

    api_client.force_authenticate(user=test_user)
    url = f"/api/leads/{sample_lead.id}/"
    response = api_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert "promo_code_details" in response.data
    assert response.data["promo_code_details"]["code"] == "PROMO1"
    assert response.data["promo_code_details"]["creator_email"] == "creator@test.com"


def test_get_lead_without_promo_code_details(api_client, test_user, sample_lead):
    api_client.force_authenticate(user=test_user)
    url = f"/api/leads/{sample_lead.id}/"
    response = api_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert "promo_code_details" in response.data
    assert response.data["promo_code_details"] is None
