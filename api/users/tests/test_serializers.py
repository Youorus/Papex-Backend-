import pytest
from rest_framework.exceptions import ValidationError

from api.users.models import User
from api.users.roles import UserRoles
from api.users.serializers import PasswordChangeSerializer, UserSerializer


@pytest.mark.django_db
def test_user_serializer_create_success():
    data = {
        "email": "test@example.com",
        "first_name": "John",
        "last_name": "Doe",
        "password": "strongpassword",
        "role": UserRoles.CONSEILLER,
    }
    serializer = UserSerializer(data=data)
    assert serializer.is_valid(), serializer.errors
    user = serializer.save()

    assert user.email == "test@example.com"
    assert user.first_name == "John"
    assert user.last_name == "Doe"
    assert user.role == UserRoles.CONSEILLER
    assert user.check_password("strongpassword")


@pytest.mark.django_db
def test_user_serializer_update_role():
    user = User.objects.create_user(
        email="update@example.com",
        first_name="Old",
        last_name="Name",
        password="password123",
        role=UserRoles.CONSEILLER,
    )
    data = {"first_name": "New", "role": UserRoles.ADMIN}
    serializer = UserSerializer(instance=user, data=data, partial=True)
    assert serializer.is_valid(), serializer.errors
    updated_user = serializer.save()
    assert updated_user.first_name == "New"
    assert updated_user.role == UserRoles.ADMIN
    assert (
        updated_user.is_superuser is True
    )  # Vérifie que les permissions sont mises à jour


@pytest.mark.django_db
def test_password_change_serializer_success():
    user = User(
        email="passchange@example.com",
        first_name="Test",
        last_name="User",
        role=UserRoles.ADMIN,
    )
    user.set_password("oldpass123")
    user.save()

    serializer = PasswordChangeSerializer(
        data={"old_password": "oldpass123", "new_password": "newpass456"},
        context={"user": user},
    )

    assert serializer.is_valid(), serializer.errors
    validated = serializer.validated_data
    assert validated["new_password"] == "newpass456"


@pytest.mark.django_db
def test_password_change_serializer_wrong_old_password():
    user = User(
        email="wrongold@example.com",
        first_name="Wrong",
        last_name="Pass",
        role=UserRoles.ADMIN,
    )
    user.set_password("correctpass")
    user.save()

    serializer = PasswordChangeSerializer(
        data={"old_password": "wrongpass", "new_password": "newpass"},
        context={"user": user},
    )

    assert not serializer.is_valid()
    assert "old_password" in serializer.errors


@pytest.mark.django_db
def test_password_change_serializer_short_new_password():
    user = User(
        email="shortpass@example.com",
        first_name="Short",
        last_name="Pass",
        role=UserRoles.CONSEILLER,
    )
    user.set_password("oldpass123")
    user.save()

    serializer = PasswordChangeSerializer(
        data={"old_password": "oldpass123", "new_password": "123"},
        context={"user": user},
    )

    assert not serializer.is_valid()
    assert "new_password" in serializer.errors
