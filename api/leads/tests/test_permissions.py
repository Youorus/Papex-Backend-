"""
Tests unitaires des permissions personnalisées de l'application Leads.

Ce fichier vérifie le bon fonctionnement des permissions suivantes :
- IsLeadCreator : seuls les utilisateurs authentifiés avec les rôles adéquats (ex. ADMIN) peuvent créer un lead.
- IsConseillerOrAdmin : seuls les utilisateurs actifs ayant les rôles CONSEILLER ou ADMIN peuvent accéder à certaines vues.

Chaque test simule une requête via APIRequestFactory pour tester les méthodes has_permission.
"""

from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from api.leads.permissions import IsConseillerOrAdmin, IsLeadCreator
from api.users.models import User
from api.users.roles import UserRoles


def test_permission_lead_creator_admin_peut_creer():
    user = User(role=UserRoles.ADMIN)
    request = APIRequestFactory().post("/leads/")
    request.user = user
    view = type("View", (), {"action": "create"})()
    assert IsLeadCreator().has_permission(request, view)


def test_permission_conseiller_non_authentifie_refuse():
    request = APIRequestFactory().post("/leads/")
    request.user = type("AnonymousUser", (), {"is_authenticated": False})()
    view = type("View", (), {"action": "create"})()
    assert not IsLeadCreator().has_permission(request, view)


def test_permission_conseiller_et_admin_autorises():
    admin = User(role=UserRoles.ADMIN, is_active=True)
    conseiller = User(role=UserRoles.CONSEILLER, is_active=True)

    factory = APIRequestFactory()
    view = type("View", (), {})()

    request_admin = factory.get("/leads/")
    request_admin.user = admin
    assert IsConseillerOrAdmin().has_permission(request_admin, view)

    request_conseiller = factory.get("/leads/")
    request_conseiller.user = conseiller
    assert IsConseillerOrAdmin().has_permission(request_conseiller, view)
