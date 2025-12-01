from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView

from api.custom_auth.views import CustomTokenRefreshView, LoginView, LogoutView

urlpatterns = [
    # Authentification JWT native
    path("token/", TokenObtainPairView.as_view(), name="api_token_obtain_pair"),
    path("token/refresh/", CustomTokenRefreshView.as_view(), name="token_refresh"),
    # Authentification "custom" (login par email/mot de passe)
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
]
