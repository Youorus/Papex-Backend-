from django.urls import path
from django.http import JsonResponse

def ping_view(request):
    return JsonResponse({"status": "ok", "message": "API online"})

urlpatterns = [
    path("", ping_view, name="ping"),
]
