import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture
def user_active():
    return User.objects.create_user(
        email="user@example.com",
        password="securepass123",
        first_name="John",
        last_name="Doe",
        role="CONSEILLER",  # ou UserRoles.CONSEILLER
        is_active=True,
    )


@pytest.fixture
def user_inactive():
    return User.objects.create_user(
        email="inactive@example.com",
        password="securepass123",
        first_name="Inactive",
        last_name="User",
        is_active=False,
    )


@pytest.fixture
def api_client():
    return APIClient()


def test_login_success(api_client, user_active):
    url = reverse("login")
    response = api_client.post(
        url, {"email": user_active.email, "password": "securepass123"}
    )

    assert response.status_code == status.HTTP_200_OK
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies
    assert response.data["role"] == user_active.role


def test_login_wrong_password(api_client, user_active):
    url = reverse("login")
    response = api_client.post(
        url, {"email": user_active.email, "password": "wrongpass"}
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "password" in response.data


def test_login_inactive_user(api_client, user_inactive):
    url = reverse("login")
    response = api_client.post(
        url, {"email": user_inactive.email, "password": "securepass123"}
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "non_field_errors" in response.data


def test_login_nonexistent_user(api_client):
    url = reverse("login")
    response = api_client.post(
        url, {"email": "nobody@example.com", "password": "anything"}
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "email" in response.data


def test_logout_deletes_cookies(api_client, user_active):
    # Simule une session active
    api_client.force_authenticate(user=user_active)
    url = reverse("logout")
    response = api_client.post(url)

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert response.cookies["access_token"].value == ""
    assert response.cookies["refresh_token"].value == ""
    assert response.cookies["user_role"].value == ""


def test_token_refresh_success(api_client, user_active):
    refresh = RefreshToken.for_user(user_active)
    api_client.cookies["refresh_token"] = str(refresh)

    url = reverse("token_refresh")
    response = api_client.post(url)

    assert response.status_code == status.HTTP_200_OK
    assert "access_token" in response.cookies
    assert "access" in response.data


def test_token_refresh_missing_cookie(api_client):
    url = reverse("token_refresh")
    response = api_client.post(url)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["detail"] == "Missing refresh token in cookies"


def test_cookie_jwt_authentication_success(user_active):
    from api.custom_auth.authentication import CookieJWTAuthentication

    token = RefreshToken.for_user(user_active).access_token
    request = type(
        "Request", (), {"COOKIES": {"access_token": str(token)}, "META": {}}
    )()

    auth = CookieJWTAuthentication()
    user, validated_token = auth.authenticate(request)
    assert user == user_active


def test_cookie_jwt_authentication_missing_token():
    from api.custom_auth.authentication import CookieJWTAuthentication

    request = type("Request", (), {"COOKIES": {}, "META": {}})()
    auth = CookieJWTAuthentication()
    assert auth.authenticate(request) is None
