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

from .models import WhatsAppMessage, WhatsAppConversationSettings
from .serializers import (
    ConversationPreviewSerializer,
    SendMessageSerializer,
    ToggleAgentSerializer,
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
        itype = interactive.get("type")
        if itype == "button_reply":
            return interactive.get("button_reply", {}).get("title", "")
        if itype == "list_reply":
            return interactive.get("list_reply", {}).get("title", "")
    media_types = {"image": "[Image]", "audio": "[Audio]", "video": "[Video]",
                   "document": "[Document]", "sticker": "[Sticker]"}
    return media_types.get(msg_type, f"[{msg_type}]")


def _process_incoming_message(msg: dict):
    wa_phone = msg.get("from", "")
    wa_id = msg.get("id", "")
    text_body = _extract_message_body(msg)

    if not wa_id or not wa_phone:
        logger.warning("Message ignore - wa_id ou wa_phone manquant")
        return

    if WhatsAppMessage.objects.filter(wa_id=wa_id).exists():
        logger.info("Message %s deja recu, ignore", wa_id)
        return

    lead = get_lead_by_phone(wa_phone)
    logger.info("Lead : %s", f"{lead.first_name} {lead.last_name}" if lead else "inconnu")

    WhatsAppMessage.objects.create(
        wa_id=wa_id,
        lead=lead,
        sender_phone=wa_phone,
        body=text_body,
        is_outbound=False,
        is_read=False,
        delivery_status="delivered",
    )

    # Confirmation RDV automatique
    if lead and text_body and ("oui" in text_body.lower() or "confirme" in text_body.lower()):
        try:
            status_confirme = LeadStatus.objects.get(code=RDV_CONFIRME)
            lead.status = status_confirme
            lead.save(update_fields=["status"])
            logger.info("Lead %s %s confirme via WhatsApp", lead.first_name, lead.last_name)
        except LeadStatus.DoesNotExist:
            logger.error("LeadStatus RDV_CONFIRME introuvable")

    _trigger_agent(text_body=text_body, sender_phone=wa_phone, lead=lead)


def _trigger_agent(text_body: str, sender_phone: str, lead):
    try:
        from .agent.handler import trigger_agent_response
        trigger_agent_response(incoming_body=text_body, sender_phone=sender_phone, lead=lead)
    except Exception as exc:
        logger.exception("Erreur agent IA (non bloquante) : %s", exc)


def _process_status_update(st: dict):
    wa_id = st.get("id")
    status_value = st.get("status")
    if not wa_id or not status_value:
        return
    try:
        msg = WhatsAppMessage.objects.get(wa_id=wa_id)
    except WhatsAppMessage.DoesNotExist:
        return
    if status_value not in {"sent", "delivered", "read", "failed"}:
        return
    msg.delivery_status = status_value
    if status_value == "read":
        msg.is_read = True
    msg.save(update_fields=["delivery_status", "is_read"])


# ─── Webhook ──────────────────────────────────────────────────────────────────

@never_cache
@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def whatsapp_webhook(request):
    if request.method == "GET":
        verify_token = getattr(settings, "WHATSAPP_VERIFY_TOKEN", "papex_secret_2026")
        mode = request.query_params.get("hub.mode")
        token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge")
        if mode == "subscribe" and token == verify_token:
            return _no_cache(HttpResponse(challenge, status=200))
        return _no_cache(HttpResponse("Forbidden", status=403))

    data = request.data
    try:
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                for msg in value.get("messages", []):
                    _process_incoming_message(msg)
                for st in value.get("statuses", []):
                    _process_status_update(st)
        return _no_cache(HttpResponse("EVENT_RECEIVED", status=200))
    except Exception as exc:
        logger.exception("Erreur Webhook WhatsApp : %s", exc)
        return _no_cache(HttpResponse("EVENT_RECEIVED", status=200))


# ─── Conversations & Messages ─────────────────────────────────────────────────

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
        .select_related("whatsapp_settings")
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
        agent_on = WhatsAppConversationSettings.is_agent_enabled(phone=phone)

        unknown.append({
            "id": None,
            "sender_phone": phone,
            "first_name": "Inconnu",
            "last_name": phone,
            "phone": phone,
            "last_message": WhatsAppMessageSerializer(last_msg).data if last_msg else None,
            "unread_count": unread,
            "is_unknown": True,
            "agent_enabled": agent_on,
        })

    def get_ts(conv):
        lm = conv.get("last_message")
        return lm["timestamp"] if lm and lm.get("timestamp") else ""

    all_conversations = sorted(list(known) + unknown, key=get_ts, reverse=True)
    return _no_cache(Response(all_conversations))


@never_cache
@api_view(["GET"])
@permission_classes([AllowAny])
def message_list(request, lead_id: int):
    messages = WhatsAppMessage.objects.filter(lead_id=lead_id).order_by("timestamp")
    return _no_cache(Response(WhatsAppMessageSerializer(messages, many=True).data))


@never_cache
@api_view(["GET"])
@permission_classes([AllowAny])
def message_list_unknown(request, phone: str):
    messages = WhatsAppMessage.objects.filter(lead__isnull=True, sender_phone=phone).order_by("timestamp")
    return _no_cache(Response(WhatsAppMessageSerializer(messages, many=True).data))


# ─── Envoi & Lecture ──────────────────────────────────────────────────────────

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
        logger.exception("Echec envoi WhatsApp : %s", exc)
        return Response({"detail": "Echec envoi via Meta.", "error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

    wa_id = meta_response.get("messages", [{}])[0].get("id", f"out_{to_phone}_{body[:8]}")
    message = WhatsAppMessage.objects.create(
        wa_id=wa_id, lead=lead, sender_phone=to_phone,
        body=body, is_outbound=True, is_read=True, delivery_status="sent",
    )
    return Response(WhatsAppMessageSerializer(message).data, status=status.HTTP_201_CREATED)


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


# ─── Toggle Agent par conversation ────────────────────────────────────────────

@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def agent_settings_lead(request, lead_id: int):
    """
    GET  /whatsapp/conversations/<lead_id>/agent/  → état agent
    POST /whatsapp/conversations/<lead_id>/agent/  → { "agent_enabled": bool }
    """
    try:
        lead = Lead.objects.get(id=lead_id)
    except Lead.DoesNotExist:
        return Response({"detail": "Lead introuvable."}, status=status.HTTP_404_NOT_FOUND)

    conv_settings = WhatsAppConversationSettings.get_for_lead(lead)

    if request.method == "GET":
        return Response({"agent_enabled": conv_settings.agent_enabled})

    serializer = ToggleAgentSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    conv_settings.agent_enabled = serializer.validated_data["agent_enabled"]
    conv_settings.save(update_fields=["agent_enabled", "updated_at"])
    logger.info("Agent %s pour lead #%d", "actif" if conv_settings.agent_enabled else "pause", lead_id)
    return Response({"agent_enabled": conv_settings.agent_enabled})


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def agent_settings_unknown(request, phone: str):
    """
    GET  /whatsapp/conversations/unknown/<phone>/agent/
    POST /whatsapp/conversations/unknown/<phone>/agent/  → { "agent_enabled": bool }
    """
    conv_settings = WhatsAppConversationSettings.get_for_phone(phone)

    if request.method == "GET":
        return Response({"agent_enabled": conv_settings.agent_enabled})

    serializer = ToggleAgentSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    conv_settings.agent_enabled = serializer.validated_data["agent_enabled"]
    conv_settings.save(update_fields=["agent_enabled", "updated_at"])
    logger.info("Agent %s pour phone=%s", "actif" if conv_settings.agent_enabled else "pause", phone)
    return Response({"agent_enabled": conv_settings.agent_enabled})