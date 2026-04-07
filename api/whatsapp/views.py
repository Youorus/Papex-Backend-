import json
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

print("🔥🔥 LE MODULE WHATSAPP EST CHARGÉ 🔥🔥")
@csrf_exempt
def whatsapp_webhook(request):
    print("🔥 WEBHOOK HIT 🔥")
    if request.method == "GET":
        # Vérification du token par Meta
        VERIFY_TOKEN = "papex_secret_2026"
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")

        if mode == "subscribe" and token == VERIFY_TOKEN:
            return HttpResponse(challenge, status=200)
        return HttpResponse("Forbidden", status=403)

    elif request.method == "POST":
        # Réception des données de messages
        try:
            data = json.loads(request.body)
            print(f"📩 Webhook WhatsApp reçu: {data}")

            # TODO: Ta logique pour traiter le message ici

            return HttpResponse("EVENT_RECEIVED", status=200)
        except Exception as e:
            return HttpResponse(str(e), status=500)

    return HttpResponse("Method Not Allowed", status=405)