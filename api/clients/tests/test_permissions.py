import pytest
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from api.clients.permissions import IsClientCreateOpen


# Vue factice avec un attribut `action` pour simuler les actions DRF
class DummyView(APIView):
    def __init__(self, action):
        self.action = action


@pytest.fixture
def factory():
    return APIRequestFactory()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "action,authenticated,expected",
    [
        ("create", False, True),  # POST anonyme autorisé
        ("create", True, True),  # POST authentifié autorisé
        ("list", False, False),  # GET anonyme interdit
        ("list", True, True),  # GET authentifié autorisé
        ("update", False, False),  # PATCH anonyme interdit
        ("update", True, True),  # PATCH authentifié autorisé
    ],
)
def test_is_client_create_open(
    action, authenticated, expected, factory, django_user_model
):
    # Création d'un utilisateur uniquement si `authenticated` est True
    if authenticated:
        user = django_user_model.objects.create_user(
            email="user@example.com",
            first_name="Test",
            last_name="User",
            password="supersecret",
        )
    else:

        class AnonymousUser:
            is_authenticated = False

        user = AnonymousUser()

    # Création de la requête
    request = factory.get("/")
    request.user = user

    # Vue simulée avec action définie
    view = DummyView(action=action)
    permission = IsClientCreateOpen()

    # Vérifie le comportement attendu
    assert permission.has_permission(request, view) is expected
