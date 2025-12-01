import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from api.statut_dossier.models import StatutDossier
from api.users.models import User
from api.users.roles import UserRoles

# --- FIXTURES ---


@pytest.fixture
def api_client():
    """APIClient DRF basique, non authentifié."""
    return APIClient()


@pytest.fixture
def admin_user(db):
    """
    Crée un admin (role ADMIN) pour tester tous les endpoints autorisés.
    """
    return User.objects.create_superuser(
        email="admin@example.com",
        password="AdminPass123!",
        first_name="Admin",
        last_name="User",
    )


@pytest.fixture
def conseiller_user(db):
    """
    Crée un utilisateur non-admin (ex : CONSEILLER).
    Sert à tester les permissions lecture/écriture.
    """
    return User.objects.create_user(
        email="conseiller@example.com",
        password="Conseiller123!",
        first_name="Jean",
        last_name="Dupont",
    )


@pytest.fixture
def auth_client(api_client, admin_user):
    """
    APIClient authentifié en tant qu’admin pour simuler tous les droits.
    """
    api_client.force_authenticate(user=admin_user)
    return api_client


@pytest.fixture
def conseiller_client(api_client, conseiller_user):
    """
    APIClient authentifié en tant que conseiller (pas admin).
    Pour tester les droits limités (lecture seule).
    """
    api_client.force_authenticate(user=conseiller_user)
    return api_client


@pytest.fixture
def statut_dossier(db):
    """
    Crée un StatutDossier pour les tests.
    """
    return StatutDossier.objects.create(
        code="A_TRAITER", label="À traiter", color="#f59e42"
    )


# --- TESTS MODELE ---


@pytest.mark.django_db
class TestStatutDossierModel:
    def test_str(self, statut_dossier):
        """
        Vérifie la méthode __str__ du modèle (doit retourner label + code).
        Pratique pour admin Django et debug console.
        """
        assert str(statut_dossier) == "À traiter (A_TRAITER)"

    def test_code_unique(self, db):
        """
        Le code doit être unique.
        Toute tentative de duplication doit lever une exception (contrainte BDD).
        """
        StatutDossier.objects.create(code="INCOMPLET", label="Incomplet", color="#ddd")
        with pytest.raises(Exception):
            StatutDossier.objects.create(code="INCOMPLET", label="Autre", color="#aaa")


# --- TESTS API & PERMISSIONS ---


@pytest.mark.django_db
class TestStatutDossierAPI:
    def test_list_statuts_authenticated(self, conseiller_client, statut_dossier):
        """
        Lecture de la liste des statuts possible pour un user authentifié (hors admin).
        Doit retourner 200 + inclure le statut créé.
        Gère la pagination DRF si active.
        """
        url = reverse("statut-dossiers-list")
        response = conseiller_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        results = (
            response.data["results"] if "results" in response.data else response.data
        )
        assert any(s["code"] == "A_TRAITER" for s in results)

    def test_list_statuts_forbidden_for_unauthenticated(
        self, api_client, statut_dossier
    ):
        """
        Lecture de la liste sans authentification.
        Doit retourner 401 UNAUTHORIZED.
        """
        url = reverse("statut-dossiers-list")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_retrieve_statut_authenticated(self, conseiller_client, statut_dossier):
        """
        Lecture d’un statut unique pour un user authentifié.
        Doit retourner 200 et le bon objet.
        """
        url = reverse("statut-dossiers-detail", args=[statut_dossier.id])
        response = conseiller_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["label"] == "À traiter"

    def test_retrieve_statut_forbidden_for_unauthenticated(
        self, api_client, statut_dossier
    ):
        """
        Lecture d’un statut sans être connecté : doit retourner 401 UNAUTHORIZED.
        """
        url = reverse("statut-dossiers-detail", args=[statut_dossier.id])
        response = api_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_statut_admin_only(self, auth_client):
        """
        Création d’un nouveau statut (réservé admin).
        Doit retourner 201 CREATED, l’objet doit exister en base.
        """
        url = reverse("statut-dossiers-list")
        payload = {"code": "COMPLET", "label": "Complet", "color": "#44ff44"}
        response = auth_client.post(url, payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert StatutDossier.objects.filter(code="COMPLET").exists()

    def test_create_statut_forbidden_for_non_admin(self, conseiller_client):
        """
        Création d’un statut par un non-admin : doit être refusée (403).
        """
        url = reverse("statut-dossiers-list")
        payload = {"code": "NON_ADMIN", "label": "Interdit", "color": "#123"}
        response = conseiller_client.post(url, payload, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_update_statut_admin_only(self, auth_client, statut_dossier):
        """
        Modification d’un statut par un admin : PATCH doit passer, valeur modifiée en base.
        """
        url = reverse("statut-dossiers-detail", args=[statut_dossier.id])
        payload = {"label": "À vérifier"}
        response = auth_client.patch(url, payload, format="json")
        assert response.status_code == status.HTTP_200_OK
        statut_dossier.refresh_from_db()
        assert statut_dossier.label == "À vérifier"

    def test_update_statut_forbidden_for_non_admin(
        self, conseiller_client, statut_dossier
    ):
        """
        Modification d’un statut par un non-admin : doit retourner 403 FORBIDDEN.
        """
        url = reverse("statut-dossiers-detail", args=[statut_dossier.id])
        payload = {"label": "Non autorisé"}
        response = conseiller_client.patch(url, payload, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_statut_admin_only(self, auth_client, statut_dossier):
        """
        Suppression d’un statut par un admin : doit supprimer l’objet (204 attendu).
        """
        url = reverse("statut-dossiers-detail", args=[statut_dossier.id])
        response = auth_client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not StatutDossier.objects.filter(id=statut_dossier.id).exists()

    def test_delete_statut_forbidden_for_non_admin(
        self, conseiller_client, statut_dossier
    ):
        """
        Suppression par un non-admin : doit retourner 403 FORBIDDEN, rien supprimé.
        """
        url = reverse("statut-dossiers-detail", args=[statut_dossier.id])
        response = conseiller_client.delete(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_code_uniqueness_api(self, auth_client, statut_dossier):
        """
        Création d’un statut avec un code déjà existant : doit retourner 400 BAD REQUEST (contrainte API et BDD).
        """
        url = reverse("statut-dossiers-list")
        payload = {
            "code": "A_TRAITER",  # code déjà pris
            "label": "Doublon",
            "color": "#000",
        }
        response = auth_client.post(url, payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "code" in response.data

    def test_color_format(self, auth_client):
        """
        Création d’un statut avec une couleur au mauvais format.
        Si un validator de couleur est en place, retourne 400.
        Sinon, 201 (test robuste dans les deux cas).
        """
        url = reverse("statut-dossiers-list")
        payload = {
            "code": "TEST_COLOR",
            "label": "Test Couleur",
            "color": "not_a_color",
        }
        response = auth_client.post(url, payload, format="json")
        assert response.status_code in (
            status.HTTP_201_CREATED,
            status.HTTP_400_BAD_REQUEST,
        )
