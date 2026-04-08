import logging
from django.http import HttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from api.leads.models import Lead
from api.lead_status.models import LeadStatus
from api.leads.constants import RDV_CONFIRME

logger = logging.getLogger(__name__)


@extend_schema(
    tags=['WhatsApp'],
    summary="Webhook WhatsApp (Vérification et Réception)",
    description="Endpoint pour la validation Meta (GET) et la réception des messages utilisateurs (POST)."
)
@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def whatsapp_webhook(request):
    """
    Gestionnaire centralisé des interactions WhatsApp.
    Identifie automatiquement le Lead par son numéro de téléphone.
    """

    # --- 1. VÉRIFICATION DU TOKEN (GET) ---
    if request.method == "GET":
        VERIFY_TOKEN = "papex_secret_2026"
        mode = request.query_params.get("hub.mode")
        token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge")

        if mode == "subscribe" and token == VERIFY_TOKEN:
            logger.info("✅ Webhook WhatsApp validé par Meta")
            return HttpResponse(challenge, status=200)

        logger.warning("❌ Échec de validation du Webhook WhatsApp")
        return HttpResponse("Forbidden", status=403)

    # --- 2. RÉCEPTION DES MESSAGES (POST) ---
    elif request.method == "POST":
        data = request.data

        try:
            # Extraction sécurisée de la structure Meta
            entries = data.get("entry", [])
            for entry in entries:
                changes = entry.get("changes", [])
                for change in changes:
                    value = change.get("value", {})
                    messages = value.get("messages", [])

                    for msg in messages:
                        wa_phone = msg.get("from")  # Format: 336...
                        text_body = msg.get("text", {}).get("body", "")
                        wa_id = msg.get("id")

                        # 🔍 Identification automatique du Lead
                        # On cherche sur les 9 derniers chiffres pour ignorer le préfixe pays
                        lead = Lead.objects.filter(phone__icontains=wa_phone[-9:]).first()


                        # 🧠 Logique métier : Auto-confirmation
                        if lead and ("oui" in text_body.lower() or "confirme" in text_body.lower()):
                            try:
                                status_confirme = LeadStatus.objects.get(code=RDV_CONFIRME)
                                lead.status = status_confirme
                                lead.save(update_fields=['status'])
                                logger.info(f"✅ Lead {lead.first_name} {lead.last_name} confirmé via WhatsApp")
                            except LeadStatus.DoesNotExist:
                                logger.error("Status RDV_CONFIRME manquant")

            # Toujours renvoyer 200 à Meta pour éviter la désactivation du webhook
            return HttpResponse("EVENT_RECEIVED", status=200)

        except Exception as e:
            logger.error(f"❌ Erreur Webhook WhatsApp : {str(e)}")
            return HttpResponse("EVENT_RECEIVED", status=200)

    return HttpResponse("Method Not Allowed", status=405)