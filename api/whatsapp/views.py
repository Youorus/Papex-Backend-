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

    media_types = {
        "image": "[Image]",
        "audio": "[Audio]",
        "video": "[Video]",
        "document": "[Document]",
        "sticker": "[Sticker]",
    }
    return media_types.get(msg_type, f"[{msg_type}]")


def _process_incoming_message(msg: dict):
    wa_phone = msg.get("from", "")
    wa_id = msg.get("id", "")
    msg_type = msg.get("type", "unknown")
    text_body = _extract_message_body(msg)

    logger.info(
        "Processing incoming WhatsApp message | wa_id=%s | from=%s | type=%s | body=%s",
        wa_id,
        wa_phone,
        msg_type,
        text_body,
    )

    if not wa_id or not wa_phone:
        logger.warning(
            "Incoming message ignored | missing wa_id or wa_phone | wa_id=%s | wa_phone=%s",
            wa_id,
            wa_phone,
        )
        return

    if WhatsAppMessage.objects.filter(wa_id=wa_id).exists():
        logger.info("Incoming message ignored | duplicate wa_id=%s", wa_id)
        return

    try:
        lead = get_lead_by_phone(wa_phone)
    except Exception as exc:
        logger.exception(
            "Lead lookup failed | wa_phone=%s | error=%s",
            wa_phone,
            exc,
        )
        lead = None

    logger.info(
        "Lead lookup result | wa_phone=%s | lead_id=%s | lead_name=%s",
        wa_phone,
        getattr(lead, "id", None),
        f"{lead.first_name} {lead.last_name}" if lead else "inconnu",
    )

    try:
        saved_message = WhatsAppMessage.objects.create(
            wa_id=wa_id,
            lead=lead,
            sender_phone=wa_phone,
            body=text_body,
            is_outbound=False,
            is_read=False,
            delivery_status="delivered",
        )
        logger.info(
            "Incoming message saved | db_id=%s | wa_id=%s | lead_id=%s",
            saved_message.id,
            wa_id,
            getattr(lead, "id", None),
        )
    except Exception as exc:
        logger.exception(
            "Failed to save incoming WhatsApp message | wa_id=%s | error=%s",
            wa_id,
            exc,
        )
        return

    if lead and text_body and ("oui" in text_body.lower() or "confirme" in text_body.lower()):
        logger.info(
            "Automatic appointment confirmation check passed | lead_id=%s | wa_id=%s",
            lead.id,
            wa_id,
        )
        try:
            status_confirme = LeadStatus.objects.get(code=RDV_CONFIRME)
            old_status = lead.status.code if lead.status else None
            lead.status = status_confirme
            lead.save(update_fields=["status"])
            logger.info(
                "Lead status updated from WhatsApp confirmation | lead_id=%s | old_status=%s | new_status=%s",
                lead.id,
                old_status,
                status_confirme.code,
            )
        except LeadStatus.DoesNotExist:
            logger.error("LeadStatus RDV_CONFIRME not found")
        except Exception as exc:
            logger.exception(
                "Failed to update lead status from WhatsApp confirmation | lead_id=%s | error=%s",
                lead.id,
                exc,
            )

    _trigger_agent(text_body=text_body, sender_phone=wa_phone, lead=lead)


def _trigger_agent(text_body: str, sender_phone: str, lead):
    logger.info(
        "Agent trigger requested | phone=%s | lead_id=%s | body=%s",
        sender_phone,
        getattr(lead, "id", None),
        text_body,
    )

    logger.info(
        "Agent global settings | enabled=%s | has_gemini_key=%s | model=%s",
        getattr(settings, "WHATSAPP_AGENT_ENABLED", False),
        bool(getattr(settings, "GEMINI_API_KEY", None)),
        getattr(settings, "GEMINI_MODEL", None),
    )

    try:
        conversation_agent_enabled = WhatsAppConversationSettings.is_agent_enabled(
            lead=lead,
            phone=sender_phone if not lead else None,
        )
        logger.info(
            "Agent conversation settings | phone=%s | lead_id=%s | enabled=%s",
            sender_phone,
            getattr(lead, "id", None),
            conversation_agent_enabled,
        )
    except Exception as exc:
        logger.exception(
            "Failed to read conversation agent settings | phone=%s | lead_id=%s | error=%s",
            sender_phone,
            getattr(lead, "id", None),
            exc,
        )

    try:
        from .agent.handler import trigger_agent_response

        logger.info(
            "Calling trigger_agent_response | phone=%s | lead_id=%s",
            sender_phone,
            getattr(lead, "id", None),
        )

        agent_result = trigger_agent_response(
            incoming_body=text_body,
            sender_phone=sender_phone,
            lead=lead,
        )

        logger.info(
            "Agent trigger completed | phone=%s | lead_id=%s | returned=%s",
            sender_phone,
            getattr(lead, "id", None),
            bool(agent_result),
        )

    except Exception as exc:
        logger.exception(
            "Erreur agent IA (non bloquante) | phone=%s | lead_id=%s | error=%s",
            sender_phone,
            getattr(lead, "id", None),
            exc,
        )


def _process_status_update(st: dict):
    wa_id = st.get("id")
    status_value = st.get("status")

    logger.info(
        "Processing WhatsApp status update | wa_id=%s | status=%s | payload=%s",
        wa_id,
        status_value,
        json.dumps(st, ensure_ascii=False),
    )

    if not wa_id or not status_value:
        logger.warning(
            "Status update ignored | missing wa_id or status | wa_id=%s | status=%s",
            wa_id,
            status_value,
        )
        return

    try:
        msg = WhatsAppMessage.objects.get(wa_id=wa_id)
    except WhatsAppMessage.DoesNotExist:
        logger.warning("Status update ignored | local message not found for wa_id=%s", wa_id)
        return
    except Exception as exc:
        logger.exception(
            "Failed to load local message for status update | wa_id=%s | error=%s",
            wa_id,
            exc,
        )
        return

    if status_value not in {"sent", "delivered", "read", "failed"}:
        logger.info(
            "Status update ignored | unsupported status=%s | wa_id=%s",
            status_value,
            wa_id,
        )
        return

    try:
        msg.delivery_status = status_value
        if status_value == "read":
            msg.is_read = True
        msg.save(update_fields=["delivery_status", "is_read"])
        logger.info(
            "Status update saved | wa_id=%s | status=%s | local_id=%s",
            wa_id,
            status_value,
            msg.id,
        )
    except Exception as exc:
        logger.exception(
            "Failed to save status update | wa_id=%s | status=%s | error=%s",
            wa_id,
            status_value,
            exc,
        )


@never_cache
@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def whatsapp_webhook(request):
    logger.info("WEBHOOK HIT | method=%s | path=%s", request.method, request.path)

    if request.method == "GET":
        verify_token = getattr(settings, "WHATSAPP_VERIFY_TOKEN", "papex_secret_2026")
        mode = request.query_params.get("hub.mode")
        token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge")

        logger.info(
            "Webhook verification request | mode=%s | token=%s | expected_token=%s | challenge=%s",
            mode,
            token,
            verify_token,
            challenge,
        )

        if mode == "subscribe" and token == verify_token:
            logger.info("Webhook verification SUCCESS")
            return _no_cache(HttpResponse(challenge, status=200))

        logger.warning("Webhook verification FAILED")
        return _no_cache(HttpResponse("Forbidden", status=403))

    try:
        logger.info("Webhook POST received")
        logger.info("Webhook raw payload: %s", json.dumps(request.data, ensure_ascii=False))

        data = request.data

        logger.info(
            "Webhook envelope | object=%s | entry_count=%d",
            data.get("object"),
            len(data.get("entry", [])),
        )

        for entry_index, entry in enumerate(data.get("entry", []), start=1):
            changes = entry.get("changes", [])
            logger.info(
                "Webhook entry #%d | changes_count=%d",
                entry_index,
                len(changes),
            )

            for change_index, change in enumerate(changes, start=1):
                field = change.get("field")
                value = change.get("value", {})

                logger.info(
                    "Webhook change #%d | field=%s | value_keys=%s",
                    change_index,
                    field,
                    list(value.keys()) if isinstance(value, dict) else [],
                )

                messages = value.get("messages", [])
                statuses = value.get("statuses", [])

                logger.info(
                    "Webhook content | messages=%d | statuses=%d",
                    len(messages),
                    len(statuses),
                )

                for msg in messages:
                    logger.info(
                        "Incoming message payload: %s",
                        json.dumps(msg, ensure_ascii=False),
                    )
                    _process_incoming_message(msg)

                for st in statuses:
                    logger.info(
                        "Incoming status payload: %s",
                        json.dumps(st, ensure_ascii=False),
                    )
                    _process_status_update(st)

        logger.info("Webhook POST handled successfully")
        return _no_cache(HttpResponse("EVENT_RECEIVED", status=200))

    except Exception as exc:
        logger.exception("Erreur Webhook WhatsApp : %s", exc)
        return _no_cache(HttpResponse("EVENT_RECEIVED", status=200))


@never_cache
@api_view(["GET"])
@permission_classes([AllowAny])
def conversation_list(request):
    logger.info("Conversation list requested")

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
            lead__isnull=True,
            sender_phone=phone,
            is_outbound=False,
            is_read=False,
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

    logger.info(
        "Conversation list built | known=%d | unknown=%d | total=%d",
        len(known),
        len(unknown),
        len(all_conversations),
    )

    return _no_cache(Response(all_conversations))


@never_cache
@api_view(["GET"])
@permission_classes([AllowAny])
def message_list(request, lead_id: int):
    logger.info("Message list requested for lead_id=%s", lead_id)
    messages = WhatsAppMessage.objects.filter(lead_id=lead_id).order_by("timestamp")
    logger.info("Message list result for lead_id=%s | count=%d", lead_id, messages.count())
    return _no_cache(Response(WhatsAppMessageSerializer(messages, many=True).data))


@never_cache
@api_view(["GET"])
@permission_classes([AllowAny])
def message_list_unknown(request, phone: str):
    logger.info("Message list requested for unknown phone=%s", phone)
    messages = WhatsAppMessage.objects.filter(
        lead__isnull=True,
        sender_phone=phone,
    ).order_by("timestamp")
    logger.info("Message list result for unknown phone=%s | count=%d", phone, messages.count())
    return _no_cache(Response(WhatsAppMessageSerializer(messages, many=True).data))


@api_view(["POST"])
@permission_classes([AllowAny])
def send_message(request):
    logger.info("Manual WhatsApp send requested | payload=%s", json.dumps(request.data, ensure_ascii=False))

    serializer = SendMessageSerializer(data=request.data)
    if not serializer.is_valid():
        logger.warning("Manual WhatsApp send invalid payload | errors=%s", serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    lead_id = serializer.validated_data.get("lead_id")
    phone = serializer.validated_data.get("phone")
    body = serializer.validated_data["body"]

    logger.info(
        "Manual WhatsApp send validated | lead_id=%s | phone=%s | body=%s",
        lead_id,
        phone,
        body,
    )

    lead = None
    if lead_id:
        try:
            lead = Lead.objects.get(id=lead_id)
            to_phone = normalize_phone_for_meta(lead.phone)
            logger.info(
                "Manual send target resolved from lead | lead_id=%s | raw_phone=%s | normalized_phone=%s",
                lead.id,
                lead.phone,
                to_phone,
            )
        except Lead.DoesNotExist:
            logger.warning("Manual send failed | lead not found | lead_id=%s", lead_id)
            return Response({"detail": "Lead introuvable."}, status=status.HTTP_404_NOT_FOUND)
    elif phone:
        to_phone = normalize_phone_for_meta(phone)
        logger.info(
            "Manual send target resolved from phone | raw_phone=%s | normalized_phone=%s",
            phone,
            to_phone,
        )
    else:
        logger.warning("Manual send failed | neither lead_id nor phone provided")
        return Response({"detail": "lead_id ou phone requis."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        logger.info("Sending WhatsApp message through Meta | to=%s", to_phone)
        meta_response = send_whatsapp_message(to_phone, body)
        logger.info("Meta send success | to=%s | response=%s", to_phone, json.dumps(meta_response, ensure_ascii=False))
    except Exception as exc:
        logger.exception("Echec envoi WhatsApp via Meta | to=%s | error=%s", to_phone, exc)
        return Response(
            {"detail": "Echec envoi via Meta.", "error": str(exc)},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    try:
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
        logger.info(
            "Outgoing message saved | local_id=%s | wa_id=%s | to=%s | lead_id=%s",
            message.id,
            wa_id,
            to_phone,
            getattr(lead, "id", None),
        )
    except Exception as exc:
        logger.exception(
            "Failed to save outgoing WhatsApp message | to=%s | error=%s",
            to_phone,
            exc,
        )
        raise

    return Response(WhatsAppMessageSerializer(message).data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([AllowAny])
def mark_as_read(request, lead_id: int):
    updated = WhatsAppMessage.objects.filter(
        lead_id=lead_id,
        is_outbound=False,
        is_read=False,
    ).update(is_read=True)

    logger.info("Messages marked as read | lead_id=%s | updated=%d", lead_id, updated)
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

    logger.info("Messages marked as read | unknown phone=%s | updated=%d", phone, updated)
    return Response({"marked_read": updated})


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def agent_settings_lead(request, lead_id: int):
    logger.info("Agent settings lead endpoint hit | method=%s | lead_id=%s", request.method, lead_id)

    try:
        lead = Lead.objects.get(id=lead_id)
    except Lead.DoesNotExist:
        logger.warning("Agent settings lead failed | lead not found | lead_id=%s", lead_id)
        return Response({"detail": "Lead introuvable."}, status=status.HTTP_404_NOT_FOUND)

    conv_settings = WhatsAppConversationSettings.get_for_lead(lead)

    if request.method == "GET":
        logger.info(
            "Agent settings lead GET | lead_id=%s | agent_enabled=%s",
            lead_id,
            conv_settings.agent_enabled,
        )
        return Response({"agent_enabled": conv_settings.agent_enabled})

    serializer = ToggleAgentSerializer(data=request.data)
    if not serializer.is_valid():
        logger.warning(
            "Agent settings lead POST invalid payload | lead_id=%s | errors=%s",
            lead_id,
            serializer.errors,
        )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    conv_settings.agent_enabled = serializer.validated_data["agent_enabled"]
    conv_settings.save(update_fields=["agent_enabled", "updated_at"])

    logger.info(
        "Agent settings lead updated | lead_id=%s | agent_enabled=%s",
        lead_id,
        conv_settings.agent_enabled,
    )
    return Response({"agent_enabled": conv_settings.agent_enabled})


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def agent_settings_unknown(request, phone: str):
    logger.info("Agent settings unknown endpoint hit | method=%s | phone=%s", request.method, phone)

    conv_settings = WhatsAppConversationSettings.get_for_phone(phone)

    if request.method == "GET":
        logger.info(
            "Agent settings unknown GET | phone=%s | agent_enabled=%s",
            phone,
            conv_settings.agent_enabled,
        )
        return Response({"agent_enabled": conv_settings.agent_enabled})

    serializer = ToggleAgentSerializer(data=request.data)
    if not serializer.is_valid():
        logger.warning(
            "Agent settings unknown POST invalid payload | phone=%s | errors=%s",
            phone,
            serializer.errors,
        )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    conv_settings.agent_enabled = serializer.validated_data["agent_enabled"]
    conv_settings.save(update_fields=["agent_enabled", "updated_at"])

    logger.info(
        "Agent settings unknown updated | phone=%s | agent_enabled=%s",
        phone,
        conv_settings.agent_enabled,
    )
    return Response({"agent_enabled": conv_settings.agent_enabled})