import pytest
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from api.users.models import User
from api.users.permissions import IsAdminRole

pytestmark = pytest.mark.django_db


class DummyView:
    pass


def get_request_with_user(user: User) -> Request:
    factory = APIRequestFactory()
    request = factory.get("/dummy")
    request.user = user
    return request


def test_is_admin_role_with_admin():
    admin = User.objects.create_user(
        email="admin@example.com",
        first_name="Admin",
        last_name="User",
        password="adminpass",
        role="ADMIN",
    )
    permission = IsAdminRole()
    request = get_request_with_user(admin)
    assert permission.has_permission(request, DummyView()) is True


def test_is_admin_role_with_conseiller():
    conseiller = User.objects.create_user(
        email="conseiller@example.com",
        first_name="Conseiller",
        last_name="User",
        password="testpass",
        role="CONSEILLER",
    )
    permission = IsAdminRole()
    request = get_request_with_user(conseiller)
    assert permission.has_permission(request, DummyView()) is False


def test_is_admin_role_with_anonymous():
    factory = APIRequestFactory()
    request = factory.get("/dummy")
    request.user = type("AnonymousUser", (), {"is_authenticated": False})()
    permission = IsAdminRole()
    assert permission.has_permission(request, DummyView()) is False
