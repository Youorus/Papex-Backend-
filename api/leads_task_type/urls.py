"""
Routes API pour les types de tâches.
"""

from rest_framework.routers import DefaultRouter

from api.leads_task_type.views import LeadTaskTypeViewSet

router = DefaultRouter()

router.register(
    r"",
    LeadTaskTypeViewSet,
    basename="lead-task-type",
)

urlpatterns = router.urls