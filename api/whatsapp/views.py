# api/whatsapp/views.py
import logging
import json
from django.conf import settings
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.db.models import Max

from api.leads.models import Lead
from api.lead_status.models import LeadStatus
from api.leads.constants import RDV_CONFIRME

from .models import WhatsAppMessage
from .serializers import (
    WhatsAppMessageSerializer,
    ConversationPreviewSerializer,
    UnknownConversationSerializer,
    SendMessageSerializer,
)
from .utils import get_lead_by_phone, normalize_phone_for_meta, send_whatsapp_message

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# WEBHOOK META
# ─────────────────────────────────────────────────────────────

@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def whatsapp_webhook(request):

    if request.method == "GET":
        verify_token = getattr(settings, "WHATSAPP_VERIFY_TOKEN", "papex_secret_2026")
        mode      = request.query_params.get("hub.mode")
        token     = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge")

        logger.info("🔔 Webhook GET reçu — mode=%s token=%s challenge=%s", mode, token, challenge)

        if mode == "subscribe" and token == verify_token:
            logger.info("✅ Webhook WhatsApp validé par Meta")
            return HttpResponse(challenge, status=200)

        logger.warning("❌ Échec validation Webhook — token reçu: %s", token)
        return HttpResponse("Forbidden", status=403)

    logger.info("📨 Webhook POST reçu de Meta")
    logger.info("📦 Payload brut : %s", json.dumps(request.data, ensure_ascii=False, indent=2))

    data = request.data
    try:
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                value    = change.get("value", {})
                messages = value.get("messages", [])

                if not messages:
                    logger.info("ℹ️  Pas de messages dans ce payload")

                for msg in messages:
                    logger.info("💬 Message reçu : %s", json.dumps(msg, ensure_ascii=False))
                    _process_incoming_message(msg)

        return HttpResponse("EVENT_RECEIVED", status=200)

    except Exception as exc:
        logger.error("❌ Erreur Webhook WhatsApp : %s", exc)
        return HttpResponse("EVENT_RECEIVED", status=200)


def _process_incoming_message(msg: dict):
    wa_phone  = msg.get("from", "")
    text_body = msg.get("text", {}).get("body", "")
    wa_id     = msg.get("id", "")

    if not wa_id or not wa_phone:
        logger.warning("⚠️  Message ignoré — wa_id ou wa_phone manquant")
        return

    if WhatsAppMessage.objects.filter(wa_id=wa_id).exists():
        logger.info("⏭️  Message %s déjà reçu, ignoré", wa_id)
        return

    lead = get_lead_by_phone(wa_phone)
    logger.info("👤 Lead : %s", f"{lead.first_name} {lead.last_name}" if lead else "inconnu")

    WhatsAppMessage.objects.create(
        wa_id=wa_id,
        lead=lead,
        sender_phone=wa_phone,
        body=text_body,
        is_outbound=False,
        is_read=False,
    )
    logger.info("✅ Message sauvegardé — phone=%s body=%s", wa_phone, text_body)

    if lead and ("oui" in text_body.lower() or "confirme" in text_body.lower()):
        try:
            status_confirme = LeadStatus.objects.get(code=RDV_CONFIRME)
            lead.status = status_confirme
            lead.save(update_fields=["status"])
            logger.info("🎯 Lead %s %s confirmé via WhatsApp", lead.first_name, lead.last_name)
        except LeadStatus.DoesNotExist:
            logger.error("❌ LeadStatus RDV_CONFIRME introuvable")


# ─────────────────────────────────────────────────────────────
# LISTE DES CONVERSATIONS
# GET /api/whatsapp/conversations/
# ─────────────────────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([AllowAny])
def conversation_list(request):
    """
    Retourne deux listes fusionnées :
    - Les leads connus qui ont des messages WhatsApp
    - Les numéros inconnus (lead=null) groupés par sender_phone
    """

    # ── 1. Conversations avec lead connu ─────────────────────
    leads = (
        Lead.objects
        .filter(whatsapp_messages__isnull=False)
        .annotate(last_msg_time=Max("whatsapp_messages__timestamp"))
        .order_by("-last_msg_time")
        .prefetch_related("whatsapp_messages")
        .distinct()
    )
    known = ConversationPreviewSerializer(leads, many=True).data

    # ── 2. Conversations avec numéros inconnus ────────────────
    unknown_phones = (
        WhatsAppMessage.objects
        .filter(lead__isnull=True)
        .values("sender_phone")
        .annotate(last_msg_time=Max("timestamp"))
        .order_by("-last_msg_time")
    )

    unknown = []
    for entry in unknown_phones:
        phone = entry["sender_phone"]
        last_msg = (
            WhatsAppMessage.objects
            .filter(lead__isnull=True, sender_phone=phone)
            .order_by("-timestamp")
            .first()
        )
        unread = WhatsAppMessage.objects.filter(
            lead__isnull=True, sender_phone=phone, is_outbound=False, is_read=False
        ).count()
        unknown.append({
            "id": None,
            "sender_phone": phone,
            "first_name": "Inconnu",
            "last_name": phone,
            "phone": phone,
            "last_message": WhatsAppMessageSerializer(last_msg).data if last_msg else None,
            "unread_count": unread,
            "is_unknown": True,
        })

    # ── 3. Fusion triée par date du dernier message ───────────
    from datetime import datetime

    def get_ts(conv):
        lm = conv.get("last_message")
        if lm and lm.get("timestamp"):
            return lm["timestamp"]
        return ""

    all_conversations = sorted(
        list(known) + unknown,
        key=get_ts,
        reverse=True,
    )

    return Response(all_conversations)


# ─────────────────────────────────────────────────────────────
# MESSAGES D'UNE CONVERSATION
# GET /api/whatsapp/conversations/<lead_id>/messages/
# GET /api/whatsapp/conversations/unknown/<phone>/messages/
# ─────────────────────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([AllowAny])
def message_list(request, lead_id: int):
    messages = WhatsAppMessage.objects.filter(lead_id=lead_id).order_by("timestamp")
    messages.filter(is_outbound=False, is_read=False).update(is_read=True)
    serializer = WhatsAppMessageSerializer(messages, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([AllowAny])
def message_list_unknown(request, phone: str):
    """Messages d'un numéro inconnu (sans lead associé)."""
    messages = WhatsAppMessage.objects.filter(
        lead__isnull=True, sender_phone=phone
    ).order_by("timestamp")
    messages.filter(is_outbound=False, is_read=False).update(is_read=True)
    serializer = WhatsAppMessageSerializer(messages, many=True)
    return Response(serializer.data)


# ─────────────────────────────────────────────────────────────
# ENVOYER UN MESSAGE
# POST /api/whatsapp/send/
# ─────────────────────────────────────────────────────────────

@api_view(["POST"])
@permission_classes([AllowAny])
def send_message(request):
    serializer = SendMessageSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    lead_id = serializer.validated_data.get("lead_id")
    phone   = serializer.validated_data.get("phone")
    body    = serializer.validated_data["body"]

    # Résolution du numéro destinataire
    lead = None
    if lead_id:
        try:
            lead = Lead.objects.get(id=lead_id)
            to_phone = normalize_phone_for_meta(lead.phone)
        except Lead.DoesNotExist:
            return Response({"detail": "Lead introuvable."}, status=status.HTTP_404_NOT_FOUND)
    elif phone:
        to_phone = normalize_phone_for_meta(phone)
    else:
        return Response({"detail": "lead_id ou phone requis."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        meta_response = send_whatsapp_message(to_phone, body)
    except Exception as exc:
        logger.error("Échec envoi WhatsApp : %s", exc)
        return Response(
            {"detail": "Échec d'envoi via Meta.", "error": str(exc)},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    wa_id = meta_response.get("messages", [{}])[0].get("id", f"out_{to_phone}_{body[:8]}")
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
# MARQUER COMME LU
# ─────────────────────────────────────────────────────────────

@api_view(["POST"])
@permission_classes([AllowAny])
def mark_as_read(request, lead_id: int):
    updated = WhatsAppMessage.objects.filter(
        lead_id=lead_id, is_outbound=False, is_read=False
    ).update(is_read=True)
    return Response({"marked_read": updated})


@api_view(["POST"])
@permission_classes([AllowAny])
def mark_as_read_unknown(request, phone: str):
    updated = WhatsAppMessage.objects.filter(
        lead__isnull=True, sender_phone=phone, is_outbound=False, is_read=False
    ).update(is_read=True)
    return Response({"marked_read": updated})