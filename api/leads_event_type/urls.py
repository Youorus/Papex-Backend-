"""
api/leads/events/urls.py
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import LeadEventTypeViewSet

router = DefaultRouter()
router.register(
    r"",
    LeadEventTypeViewSet,
    basename="lead-event-types",
)

urlpatterns = [
    path("", include(router.urls)),
]