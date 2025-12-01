from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .me_views import MeView
from .views import UserViewSet

router = DefaultRouter()
router.register(r"", UserViewSet, basename="users")

urlpatterns = [
    path("me/", MeView.as_view(), name="me"),
    path("", include(router.urls)),
]