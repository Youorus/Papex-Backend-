import pytest
from django.contrib.auth.models import AnonymousUser
from rest_framework.permissions import SAFE_METHODS
from rest_framework.test import APIRequestFactory

from api.contracts.permissions import IsContractEditor
from api.users.models import User
from api.users.roles import UserRoles


@pytest.fixture
def user_factory():
    """
    Fabrique un utilisateur avec tous les champs requis.
    """

    def create_user(role):
        return User.objects.create_user(
            email=f"{role.lower()}@tds.fr",
            password="12345678",
            first_name="Jean",
            last_name="Test",
            role=role,
        )

    return create_user


@pytest.mark.parametrize(
    "role",
    [
        UserRoles.ADMIN,
        UserRoles.CONSEILLER,
        UserRoles.JURISTE,
        UserRoles.ACCUEIL,
    ],
)
@pytest.mark.parametrize("method", SAFE_METHODS)
@pytest.mark.django_db
def test_contract_permission_safe_methods_all_roles(role, method, user_factory):
    """
    Tous les utilisateurs authentifiés ont accès en lecture (SAFE_METHODS), quel que soit leur rôle.
    """
    user = user_factory(role)
    factory = APIRequestFactory()
    request = factory.generic(method, "/fake-url/")
    request.user = user

    permission = IsContractEditor()
    assert permission.has_permission(request, view=None) is True


@pytest.mark.parametrize(
    "role, expected",
    [
        (UserRoles.ADMIN, True),
        (UserRoles.CONSEILLER, True),
        (UserRoles.JURISTE, True),
        (UserRoles.ACCUEIL, False),
    ],
)
@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
@pytest.mark.django_db
def test_contract_permission_write_methods(role, expected, method, user_factory):
    """
    Seuls ADMIN, JURISTE, CONSEILLER peuvent effectuer des requêtes en écriture.
    """
    user = user_factory(role)
    factory = APIRequestFactory()
    request = factory.generic(method, "/fake-url/")
    request.user = user

    permission = IsContractEditor()
    assert permission.has_permission(request, view=None) is expected


@pytest.mark.django_db
def test_contract_permission_unauthenticated_user():
    """
    Aucun accès (même en lecture) pour utilisateur non authentifié.
    """
    factory = APIRequestFactory()
    request = factory.get("/fake-url/")
    request.user = AnonymousUser()

    permission = IsContractEditor()
    assert permission.has_permission(request, view=None) is False
