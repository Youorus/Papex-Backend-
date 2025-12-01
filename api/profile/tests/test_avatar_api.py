import io
import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from api.users.models import User, UserRoles


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="test@user.com",
        first_name="Marc",
        last_name="Nkue",
        password="pwd",
        role=UserRoles.ADMIN,
    )


@pytest.fixture
def api_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
class TestUserAvatarAPI:

    def test_post_method_not_allowed(self, api_client, user):
        url = reverse("user-avatar-detail", args=[user.id])
        resp = api_client.post(url)
        assert resp.status_code == 405
        assert "non autorisée" in str(resp.data["detail"])

    def test_patch_avatar_success(self, api_client, user, mocker):
        url = reverse("user-avatar-detail", args=[user.id])

        # Mock put_object (upload)
        mocker.patch("api.profile.views.put_object")
        # Mock generate_presigned_url
        mocker.patch(
            "api.users.serializers.generate_presigned_url",
            return_value="https://cloud.test/avatars/marc/avatar.jpg"
        )

        file_content = io.BytesIO(b"avatar-image")
        file_content.name = "avatar.jpg"
        file_content.content_type = "image/jpeg"

        resp = api_client.patch(url, {"avatar": file_content}, format="multipart")

        assert resp.status_code == 200
        assert "avatar_url" in resp.data
        assert resp.data["avatar_url"].startswith("https://cloud.test/avatars/")

    def test_patch_avatar_no_file(self, api_client, user):
        url = reverse("user-avatar-detail", args=[user.id])
        resp = api_client.patch(url, {}, format="multipart")
        assert resp.status_code == 400
        assert "Aucun fichier reçu" in resp.data["detail"]

    def test_delete_avatar_success(self, api_client, user, mocker):
        url = reverse("user-avatar-detail", args=[user.id])
        user.avatar = "marc_nkue/avatar.jpg"
        user.save()

        mocker.patch("api.profile.views.delete_object")

        resp = api_client.delete(url)
        assert resp.status_code == 204
        user.refresh_from_db()
        assert user.avatar is None

    def test_permission_required(self, db):
        user = User.objects.create_user(
            email="test2@user.com",
            first_name="Paul",
            last_name="Martin",
            password="pwd",
            role=UserRoles.ADMIN,
        )
        client = APIClient()
        url = reverse("user-avatar-detail", args=[user.id])

        resp = client.patch(url, {}, format="multipart")
        assert resp.status_code in (401, 403)

        resp = client.delete(url)
        assert resp.status_code in (401, 403)


@pytest.mark.django_db
class TestUserAvatarSerializer:
    def test_avatar_url_generation(self, user, mocker):
        from api.profile.serializers import UserAvatarSerializer

        user.avatar = "marc/avatar.jpg"
        mocker.patch(
            "api.profile.serializers.generate_presigned_url",
            return_value="https://cloud.test/avatars/marc/avatar.jpg"
        )

        serializer = UserAvatarSerializer(user)
        data = serializer.data

        assert data["avatar_url"] == "https://cloud.test/avatars/marc/avatar.jpg"