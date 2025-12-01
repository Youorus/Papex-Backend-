# api/booking/urls.py
from django.urls import path

from api.booking import views

app_name = "booking"

urlpatterns = [
    path("slots/", views.slots_for_date, name="slots-for-date"),
    path("book/", views.public_book, name="public-book"),
]
