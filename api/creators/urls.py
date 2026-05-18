from django.urls import path, include
from rest_framework.routers import DefaultRouter

from api.creators.views import CreatorProfileViewSet, SocialAccountLeadViewSet

router = DefaultRouter()
router.register(r"creators", CreatorProfileViewSet, basename="creator")
router.register(r"social-leads", SocialAccountLeadViewSet, basename="social-lead")

urlpatterns = [
    path("", include(router.urls)),
]
