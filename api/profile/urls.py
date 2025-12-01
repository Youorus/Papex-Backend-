# api/urls/urls.py

from rest_framework.routers import DefaultRouter

from api.profile.views import UserAvatarViewSet

router = DefaultRouter()
router.register(r"", UserAvatarViewSet, basename="user-avatar")

urlpatterns = router.urls
