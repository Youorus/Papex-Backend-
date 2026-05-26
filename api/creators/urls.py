from django.urls import path, include
from rest_framework.routers import DefaultRouter

from api.creators.views import CreatorProfileViewSet, SocialAccountLeadViewSet, PromoCodeViewSet, CreatorContractViewSet

router = DefaultRouter()
router.register(r"creators", CreatorProfileViewSet, basename="creator")
router.register(r"social-leads", SocialAccountLeadViewSet, basename="social-lead")
router.register(r"promo-codes", PromoCodeViewSet, basename="promo-code")
router.register(r"creator-contracts", CreatorContractViewSet, basename="creator-contract")

urlpatterns = [
    path("", include(router.urls)),
]
