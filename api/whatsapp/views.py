# api/whatsapp/views.py
import logging
from django.conf import settings
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from api.leads.models import Lead
from api.lead_status.models import LeadStatus
from api.leads.constants import RDV_CONFIRME

from .models import WhatsAppMessage
from .serializers import (
    WhatsAppMessageSerializer,
    ConversationPreviewSerializer,
    SendMessageSerializer,
)
from .utils import get_lead_by_phone, normalize_phone_for_meta, send_whatsapp_message

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# WEBHOOK META  (GET = vérification / POST = réception)
# AllowAny obligatoire — Meta ne s'authentifie pas
# ─────────────────────────────────────────────────────────────

@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def whatsapp_webhook(request):

    if request.method == "GET":
        verify_token = getattr(settings, "WHATSAPP_VERIFY_TOKEN", "papex_secret_2026")
        mode      = request.query_params.get("hub.mode")
        token     = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge")

        if mode == "subscribe" and token == verify_token:
            logger.info("Webhook WhatsApp validé par Meta")
            return HttpResponse(challenge, status=200)

        logger.warning("Échec validation Webhook WhatsApp")
        return HttpResponse("Forbidden", status=403)

    try:
        for entry in request.data.get("entry", []):
            for change in entry.get("changes", []):
                value    = change.get("value", {})
                messages = value.get("messages", [])
                for msg in messages:
                    _process_incoming_message(msg)

        return HttpResponse("EVENT_RECEIVED", status=200)

    except Exception as exc:
        logger.error("Erreur Webhook WhatsApp : %s", exc)
        return HttpResponse("EVENT_RECEIVED", status=200)


def _process_incoming_message(msg: dict):
    wa_phone  = msg.get("from", "")
    text_body = msg.get("text", {}).get("body", "")
    wa_id     = msg.get("id", "")

    if not wa_id or not wa_phone:
        return

    if WhatsAppMessage.objects.filter(wa_id=wa_id).exists():
        return

    lead = get_lead_by_phone(wa_phone)

    WhatsAppMessage.objects.create(
        wa_id=wa_id,
        lead=lead,
        sender_phone=wa_phone,
        body=text_body,
        is_outbound=False,
        is_read=False,
    )

    logger.info(
        "Message reçu de %s (lead: %s)",
        wa_phone,
        f"{lead.first_name} {lead.last_name}" if lead else "inconnu",
    )

    if lead and ("oui" in text_body.lower() or "confirme" in text_body.lower()):
        try:
            status_confirme = LeadStatus.objects.get(code=RDV_CONFIRME)
            lead.status = status_confirme
            lead.save(update_fields=["status"])
            logger.info("Lead %s %s confirmé via WhatsApp", lead.first_name, lead.last_name)
        except LeadStatus.DoesNotExist:
            logger.error("LeadStatus RDV_CONFIRME introuvable")


# ─────────────────────────────────────────────────────────────
# LISTE DES CONVERSATIONS — IsAuthenticated
# ─────────────────────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([AllowAny])
def conversation_list(request):
    lead_ids = (
        WhatsAppMessage.objects
        .values_list("lead_id", flat=True)
        .distinct()
    )
    leads = (
        Lead.objects
        .filter(id__in=lead_ids)
        .prefetch_related("whatsapp_messages")
        .order_by("-whatsapp_messages__timestamp")
        .distinct()
    )
    serializer = ConversationPreviewSerializer(leads, many=True)
    return Response(serializer.data)


# ─────────────────────────────────────────────────────────────
# MESSAGES D'UNE CONVERSATION — IsAuthenticated
# ─────────────────────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([AllowAny])
def message_list(request, lead_id: int):
    messages = WhatsAppMessage.objects.filter(lead_id=lead_id).order_by("timestamp")
    messages.filter(is_outbound=False, is_read=False).update(is_read=True)
    serializer = WhatsAppMessageSerializer(messages, many=True)
    return Response(serializer.data)


# ─────────────────────────────────────────────────────────────
# ENVOYER UN MESSAGE — IsAuthenticated
# ─────────────────────────────────────────────────────────────

@api_view(["POST"])
@permission_classes([AllowAny])
def send_message(request):
    serializer = SendMessageSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    lead_id = serializer.validated_data["lead_id"]
    body    = serializer.validated_data["body"]

    try:
        lead = Lead.objects.get(id=lead_id)
    except Lead.DoesNotExist:
        return Response({"detail": "Lead introuvable."}, status=status.HTTP_404_NOT_FOUND)

    if not lead.phone:
        return Response(
            {"detail": "Ce lead n'a pas de numéro de téléphone."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    to_phone = normalize_phone_for_meta(lead.phone)

    try:
        meta_response = send_whatsapp_message(to_phone, body)
    except Exception as exc:
        logger.error("Échec envoi WhatsApp au lead %s : %s", lead_id, exc)
        return Response(
            {"detail": "Échec d'envoi via Meta.", "error": str(exc)},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    wa_id = meta_response.get("messages", [{}])[0].get("id", f"out_{lead_id}_{body[:8]}")
    message = WhatsAppMessage.objects.create(
        wa_id=wa_id,
        lead=lead,
        sender_phone=to_phone,
        body=body,
        is_outbound=True,
        is_read=True,
        delivery_status="sent",
    )

    return Response(WhatsAppMessageSerializer(message).data, status=status.HTTP_201_CREATED)


# ─────────────────────────────────────────────────────────────
# MARQUER COMME LU — IsAuthenticated
# ─────────────────────────────────────────────────────────────

@api_view(["POST"])
@permission_classes([AllowAny])
def mark_as_read(request, lead_id: int):
    updated = WhatsAppMessage.objects.filter(
        lead_id=lead_id, is_outbound=False, is_read=False
    ).update(is_read=True)
    return Response({"marked_read": updated})