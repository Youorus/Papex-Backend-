import pytest
from django.contrib.auth import get_user_model

from api.users.roles import UserRoles

User = get_user_model()


@pytest.mark.django_db
def test_create_user():
    user = User.objects.create_user(
        email="test@example.com",
        first_name="Jean",
        last_name="Dupont",
        password="azerty123",
        role=UserRoles.CONSEILLER,
    )

    assert user.email == "test@example.com"
    assert user.first_name == "Jean"
    assert user.last_name == "Dupont"
    assert user.role == UserRoles.CONSEILLER
    assert user.check_password("azerty123")
    assert user.is_staff is True
    assert user.is_superuser is False
    assert str(user) == f"test@example.com (Jean Dupont)"


@pytest.mark.django_db
def test_create_superuser():
    superuser = User.objects.create_superuser(
        email="admin@example.com",
        first_name="Admin",
        last_name="Root",
        password="adminpass",
    )

    assert superuser.is_staff is True
    assert superuser.is_superuser is True
    assert superuser.role == UserRoles.ADMIN
    assert superuser.check_password("adminpass")
