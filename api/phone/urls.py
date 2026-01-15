from django.urls import path
from .views import ClickToCallView

urlpatterns = [
    path('click-to-call/', ClickToCallView.as_view(), name='click_to_call'),
]