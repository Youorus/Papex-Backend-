from rest_framework.routers import DefaultRouter

from api.comments.views import CommentViewSet

router = DefaultRouter()
router.register(r"", CommentViewSet, basename="comments")

urlpatterns = router.urls
