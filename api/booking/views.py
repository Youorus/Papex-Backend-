from datetime import datetime

from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from api.booking.services import list_slots_with_quota, try_book_slot
from api.leads.constants import RDV_PLANIFIE
from api.leads.models import LeadStatus
from api.leads.serializers import LeadSerializer


@api_view(["GET"])
@permission_classes([AllowAny])
def slots_for_date(request):
    """
    GET /api/booking/slots/?date=YYYY-MM-DD
    -> [{ start_at, time, capacity, booked, remaining, is_full }]
    """
    ds = request.query_params.get("date")
    d = parse_date(ds) if ds else None
    if not d:
        return Response(
            {"detail": "Paramètre 'date' requis au format YYYY-MM-DD."}, status=400
        )

    data = list_slots_with_quota(d)
    return Response(data)


@api_view(["POST"])
@permission_classes([AllowAny])
def public_book(request):
    """
    POST /api/booking/book/
    body: { first_name, last_name, email?, phone, date:'YYYY-MM-DD', time:'HH:mm' }

    1) Réserve le quota du créneau (409 si plein)
    2) Crée le Lead (status RDV_PLANIFIE, appointment_date = start_at)
    """
    payload = request.data
    date_s = payload.get("date")
    time_s = payload.get("time")
    if not (date_s and time_s):
        return Response({"detail": "Champs 'date' et 'time' requis."}, status=400)

    try:
        start_at = timezone.make_aware(datetime.fromisoformat(f"{date_s}T{time_s}:00"))
    except Exception:
        return Response({"detail": "Format date/heure invalide."}, status=400)

    # 1) réservation quota
    try:
        try_book_slot(start_at)
    except ValueError as e:
        return Response({"detail": str(e)}, status=409)

    # 2) création du lead (tu peux réutiliser ta route public-create si tu y injectes try_book_slot)
    status_pk = LeadStatus.objects.get(code=RDV_PLANIFIE).pk
    ser = LeadSerializer(
        data={
            "first_name": payload.get("first_name"),
            "last_name": payload.get("last_name"),
            "email": payload.get("email"),
            "phone": payload.get("phone"),
            "appointment_date": start_at,
            "status": status_pk,
        }
    )
    ser.is_valid(raise_exception=True)
    lead = ser.save()

    return Response(LeadSerializer(lead).data, status=status.HTTP_201_CREATED)
