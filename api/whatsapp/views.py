import json
import logging

from django.conf import settings
from django.db.models import Max
from django.http import HttpResponse
from django.views.decorators.cache import never_cache

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from api.leads.constants import RDV_CONFIRME
from api.lead_status.models import LeadStatus
from api.leads.models import Lead

from .models import WhatsAppMessage
from .serializers import (
    ConversationPreviewSerializer,
    SendMessageSerializer,
    WhatsAppMessageSerializer,
)
from .utils import get_lead_by_phone, normalize_phone_for_meta, send_whatsapp_message

logger = logging.getLogger(__name__)


def _no_cache(response):
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    return response


def _extract_message_body(msg: dict) -> str:
    msg_type = msg.get("type", "text")

    if msg_type == "text":
        return msg.get("text", {}).get("body", "")

    if msg_type == "button":
        return msg.get("button", {}).get("text", "")

    if msg_type == "interactive":
        interactive = msg.get("interactive", {})
        interactive_type = interactive.get("type")

        if interactive_type == "button_reply":
            return interactive.get("button_reply", {}).get("title", "")

        if interactive_type == "list_reply":
            return interactive.get("list_reply", {}).get("title", "")

    if msg_type == "image":
        return "[Image]"
    if msg_type == "audio":
        return "[Audio]"
    if msg_type == "video":
        return "[Video]"
    if msg_type == "document":
        return "[Document]"
    if msg_type == "sticker":
        return "[Sticker]"

    return f"[{msg_type}]"


def _process_incoming_message(msg: dict):
    wa_phone = msg.get("from", "")
    wa_id = msg.get("id", "")
    text_body = _extract_message_body(msg)

    if not wa_id or not wa_phone:
        logger.warning("⚠️ Message ignoré — wa_id ou wa_phone manquant")
        return

    if WhatsAppMessage.objects.filter(wa_id=wa_id).exists():
        logger.info("⏭️ Message %s déjà reçu, ignoré", wa_id)
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
        delivery_status="delivered",
    )
    logger.info("✅ Message sauvegardé — phone=%s body=%s", wa_phone, text_body)

    if lead and text_body and ("oui" in text_body.lower() or "confirme" in text_body.lower()):
        try:
            status_confirme = LeadStatus.objects.get(code=RDV_CONFIRME)
            lead.status = status_confirme
            lead.save(update_fields=["status"])
            logger.info("🎯 Lead %s %s confirmé via WhatsApp", lead.first_name, lead.last_name)
        except LeadStatus.DoesNotExist:
            logger.error("❌ LeadStatus RDV_CONFIRME introuvable")


def _process_status_update(st: dict):
    wa_id = st.get("id")
    status_value = st.get("status")

    if not wa_id or not status_value:
        logger.warning("⚠️ Status ignoré — id ou status manquant")
        return

    try:
        msg = WhatsAppMessage.objects.get(wa_id=wa_id)
    except WhatsAppMessage.DoesNotExist:
        logger.warning("⚠️ Aucun message local trouvé pour wa_id=%s", wa_id)
        return

    allowed_statuses = {"sent", "delivered", "read", "failed"}
    if status_value not in allowed_statuses:
        logger.info("ℹ️ Status non géré: %s pour %s", status_value, wa_id)
        return

    msg.delivery_status = status_value
    if status_value == "read":
        msg.is_read = True
    msg.save(update_fields=["delivery_status", "is_read"])
    logger.info("✅ Status mis à jour — wa_id=%s status=%s", wa_id, status_value)


@never_cache
@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def whatsapp_webhook(request):
    if request.method == "GET":
        verify_token = getattr(settings, "WHATSAPP_VERIFY_TOKEN", "papex_secret_2026")
        mode = request.query_params.get("hub.mode")
        token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge")

        logger.info("🔔 Webhook GET reçu — mode=%s token=%s challenge=%s", mode, token, challenge)

        if mode == "subscribe" and token == verify_token:
            logger.info("✅ Webhook WhatsApp validé par Meta")
            return _no_cache(HttpResponse(challenge, status=200))

        logger.warning("❌ Échec validation Webhook — token reçu: %s", token)
        return _no_cache(HttpResponse("Forbidden", status=403))

    logger.info("📨 Webhook POST reçu de Meta")
    logger.info("📦 Payload brut : %s", json.dumps(request.data, ensure_ascii=False, indent=2))

    data = request.data
    try:
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                messages = value.get("messages", [])
                statuses = value.get("statuses", [])

                if not messages and not statuses:
                    logger.info("ℹ️ Pas de messages ni de statuts dans ce payload")

                for msg in messages:
                    logger.info("💬 Message reçu : %s", json.dumps(msg, ensure_ascii=False))
                    _process_incoming_message(msg)

                for st in statuses:
                    logger.info("📬 Status reçu : %s", json.dumps(st, ensure_ascii=False))
                    _process_status_update(st)

        return _no_cache(HttpResponse("EVENT_RECEIVED", status=200))

    except Exception as exc:
        logger.exception("❌ Erreur Webhook WhatsApp : %s", exc)
        return _no_cache(HttpResponse("EVENT_RECEIVED", status=200))


@never_cache
@api_view(["GET"])
@permission_classes([AllowAny])
def conversation_list(request):
    leads = (
        Lead.objects
        .filter(whatsapp_messages__isnull=False)
        .annotate(last_msg_time=Max("whatsapp_messages__timestamp"))
        .order_by("-last_msg_time")
        .prefetch_related("whatsapp_messages")
        .distinct()
    )
    known = ConversationPreviewSerializer(leads, many=True).data

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

    def get_ts(conv):
        lm = conv.get("last_message")
        if lm and lm.get("timestamp"):
            return lm["timestamp"]
        return ""

    all_conversations = sorted(list(known) + unknown, key=get_ts, reverse=True)
    return _no_cache(Response(all_conversations))


@never_cache
@api_view(["GET"])
@permission_classes([AllowAny])
def message_list(request, lead_id: int):
    messages = WhatsAppMessage.objects.filter(lead_id=lead_id).order_by("timestamp")
    serializer = WhatsAppMessageSerializer(messages, many=True)
    return _no_cache(Response(serializer.data))


@never_cache
@api_view(["GET"])
@permission_classes([AllowAny])
def message_list_unknown(request, phone: str):
    messages = WhatsAppMessage.objects.filter(
        lead__isnull=True,
        sender_phone=phone,
    ).order_by("timestamp")
    serializer = WhatsAppMessageSerializer(messages, many=True)
    return _no_cache(Response(serializer.data))


@api_view(["POST"])
@permission_classes([AllowAny])
def send_message(request):
    serializer = SendMessageSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    lead_id = serializer.validated_data.get("lead_id")
    phone = serializer.validated_data.get("phone")
    body = serializer.validated_data["body"]

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
        logger.exception("❌ Échec envoi WhatsApp : %s", exc)
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


@api_view(["POST"])
@permission_classes([AllowAny])
def mark_as_read(request, lead_id: int):
    updated = WhatsAppMessage.objects.filter(
        lead_id=lead_id,
        is_outbound=False,
        is_read=False,
    ).update(is_read=True)
    return Response({"marked_read": updated})


@api_view(["POST"])
@permission_classes([AllowAny])
def mark_as_read_unknown(request, phone: str):
    updated = WhatsAppMessage.objects.filter(
        lead__isnull=True,
        sender_phone=phone,
        is_outbound=False,
        is_read=False,
    ).update(is_read=True)
    return Response({"marked_read": updated})