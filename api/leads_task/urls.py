"""
api/leads_task/urls.py

Routes API pour les tâches de leads.
"""

from rest_framework.routers import DefaultRouter

from .views import LeadTaskViewSet

router = DefaultRouter()

router.register(
    r"",
    LeadTaskViewSet,
    basename="lead-task",
)

urlpatterns = router.urls