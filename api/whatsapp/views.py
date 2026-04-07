# api/whatsapp/views.py
import json
from django.http import HttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import extend_schema

print("🔥🔥 LE MODULE WHATSAPP EST CHARGÉ 🔥🔥")


@extend_schema(exclude=True)  # Optionnel: masquer la vérification GET si tu veux
@api_view(['GET', 'POST'])
@permission_classes([AllowAny])  # Important pour Meta qui n'a pas tes tokens de session
def whatsapp_webhook(request):
    """
    Webhook pour la réception des messages WhatsApp de Meta.
    """
    print("🔥 WEBHOOK HIT 🔥")

    if request.method == "GET":
        # Vérification du token par Meta (hub.mode, hub.verify_token, hub.challenge)
        VERIFY_TOKEN = "papex_secret_2026"
        mode = request.query_params.get("hub.mode")
        token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge")

        if mode == "subscribe" and token == VERIFY_TOKEN:
            return HttpResponse(challenge, status=200)
        return HttpResponse("Forbidden", status=403)

    elif request.method == "POST":
        try:
            # DRF met déjà le JSON parsé dans request.data
            data = request.data
            print(f"📩 Webhook WhatsApp reçu: {data}")

            # Ta logique ici
            return HttpResponse("EVENT_RECEIVED", status=200)
        except Exception as e:
            return HttpResponse(str(e), status=500)

    return HttpResponse("Method Not Allowed", status=405)