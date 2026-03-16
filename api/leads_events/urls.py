"""
api/leads/events/urls.py
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import LeadEventViewSet

router = DefaultRouter()
router.register(
    r"",
    LeadEventViewSet,
    basename="lead-events",
)

urlpatterns = [
    path("", include(router.urls)),
]