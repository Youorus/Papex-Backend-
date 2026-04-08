"""
api/leads_task/urls.py
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import LeadTaskViewSet, LeadTaskCommentViewSet

router = DefaultRouter()
router.register(r"lead-tasks", LeadTaskViewSet, basename="lead-tasks")
router.register(r"lead-task-comments", LeadTaskCommentViewSet, basename="lead-task-comments")

urlpatterns = [
    path("", include(router.urls)),
]