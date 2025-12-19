
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from api.candidate.views import CandidateViewSet

router = DefaultRouter()
router.register(r"", CandidateViewSet, basename="candidates")

urlpatterns = [
    path("", include(router.urls)),
]