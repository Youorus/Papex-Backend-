import pytest
from rest_framework.test import APIRequestFactory

from api.payments.permissions import IsPaymentEditor
from api.users.models import User, UserRoles

pytestmark = pytest.mark.django_db


@pytest.fixture
def factory():
    return APIRequestFactory()


@pytest.mark.parametrize("method", ["GET", "HEAD", "OPTIONS"])
@pytest.mark.parametrize("role", UserRoles.values)
def test_safe_methods_allowed_for_authenticated_users(factory, method, role):
    user = User(role=role)
    user.set_password("dummy")  # just to simulate auth user creation
    user.save()
    request = factory.generic(method, "/fake-url")
    request.user = user
    request._force_user = user  # required by some DRF internals

    permission = IsPaymentEditor()
    assert permission.has_permission(request, view=None)


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
@pytest.mark.parametrize(
    "role, expected",
    [
        (UserRoles.ADMIN, True),
        (UserRoles.JURISTE, True),
        (UserRoles.CONSEILLER, True),
        (UserRoles.ACCUEIL, False),
    ],
)
def test_write_methods_restricted_to_specific_roles(factory, method, role, expected):
    user = User(role=role)
    user.set_password("dummy")  # just to simulate auth user creation
    user.save()
    request = factory.generic(method, "/fake-url")
    request.user = user
    request._force_user = user  # required by some DRF internals

    permission = IsPaymentEditor()
    assert permission.has_permission(request, view=None) == expected


@pytest.mark.parametrize("method", ["GET", "POST", "PUT", "DELETE"])
def test_all_methods_for_anonymous_user(factory, method):
    request = factory.generic(method, "/fake-url")
    request.user = type("Anon", (), {"is_authenticated": False})()

    permission = IsPaymentEditor()
    assert permission.has_permission(request, view=None) is False
