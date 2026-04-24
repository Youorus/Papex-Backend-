import json
import logging
import uuid

from django.conf import settings
from django.core.cache import cache
from django.db.models import Max, Prefetch
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

# Délai debounce en secondes
AGENT_DEBOUNCE_SECONDS = getattr(settings, "KEMORA_DEBOUNCE_SECONDS", 4)

# Types de messages qui ne doivent pas déclencher l'agent ni être sauvegardés
IGNORED_MESSAGE_TYPES = {"reaction", "unsupported"}


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
    wa_phone  = msg.get("from", "")
    wa_id     = msg.get("id", "")
    msg_type  = msg.get("type", "unknown")
    text_body = _extract_message_body(msg)

    logger.info(
        "Traitement du message WhatsApp entrant | wa_id=%s | from=%s | type=%s | body=%s",
        wa_id, wa_phone, msg_type, text_body,
    )

    # ── Ignorer les types qui ne méritent pas de réponse IA ──────────────────
    if msg_type in IGNORED_MESSAGE_TYPES:
        logger.info(
            "Message ignoré (type non traitable) | wa_id=%s | type=%s",
            wa_id, msg_type,
        )
        return

    if not wa_id or not wa_phone:
        logger.warning(
            "Message entrant ignoré | wa_id ou wa_phone manquant | wa_id=%s | wa_phone=%s",
            wa_id, wa_phone,
        )
        return

    # Déduplication
    if WhatsAppMessage.objects.filter(wa_id=wa_id).exists():
        logger.info("Message entrant ignoré | wa_id dupliqué=%s", wa_id)
        return

    try:
        lead = get_lead_by_phone(wa_phone)
    except Exception as exc:
        logger.exception("Échec recherche lead | wa_phone=%s | error=%s", wa_phone, exc)
        lead = None

    logger.info(
        "Résultat de la recherche de prospect | wa_phone=%s | lead_id=%s | lead_name=%s",
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
            "Message entrant enregistré | db_id=%s | wa_id=%s | lead_id=%s",
            saved_message.id, wa_id, getattr(lead, "id", None),
        )
    except Exception as exc:
        logger.exception(
            "Échec sauvegarde message WhatsApp entrant | wa_id=%s | error=%s", wa_id, exc,
        )
        return

    # Confirmation automatique de RDV
    if lead and text_body and ("oui" in text_body.lower() or "confirme" in text_body.lower()):
        try:
            status_confirme = LeadStatus.objects.get(code=RDV_CONFIRME)
            old_status = lead.status.code if lead.status else None
            lead.status = status_confirme
            lead.save(update_fields=["status"])
            logger.info(
                "Statut lead mis à jour via confirmation WhatsApp | lead_id=%s | %s → %s",
                lead.id, old_status, status_confirme.code,
            )
        except LeadStatus.DoesNotExist:
            logger.error("LeadStatus RDV_CONFIRME introuvable")
        except Exception as exc:
            logger.exception(
                "Échec mise à jour statut lead | lead_id=%s | error=%s", lead.id, exc,
            )

    # ── Vérification agent_enabled AVANT de dispatcher ───────────────────────
    agent_active = WhatsAppConversationSettings.is_agent_enabled(lead=lead, phone=wa_phone)

    if not agent_active:
        logger.info(
            "Agent désactivé pour cette conversation — pas de réponse automatique | phone=%s | lead_id=%s",
            wa_phone,
            getattr(lead, "id", None),
        )
        return

    # ── Debounce + dispatch ───────────────────────────────────────────────────
    _schedule_debounced_agent(
        text_body=text_body,
        sender_phone=wa_phone,
        lead=lead,
        wa_message_id=wa_id,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Debounce : un seul appel Gemini par burst de messages
# ─────────────────────────────────────────────────────────────────────────────

def _debounce_cache_key(sender_phone: str) -> str:
    return f"kemora_debounce_{sender_phone}"


def _eta_from_now(seconds: int):
    from django.utils import timezone
    import datetime
    return timezone.now() + datetime.timedelta(seconds=seconds)


def _schedule_debounced_agent(
    text_body: str,
    sender_phone: str,
    lead,
    wa_message_id: str,
) -> None:
    token = str(uuid.uuid4())
    cache_key = _debounce_cache_key(sender_phone)
    cache.set(cache_key, token, timeout=60)

    logger.info(
        "Jeton de délai défini | téléphone=%s | jeton=%s | délai=%ds",
        sender_phone, token, AGENT_DEBOUNCE_SECONDS,
    )

    _dispatch_agent_q2(
        text_body=text_body,
        sender_phone=sender_phone,
        lead=lead,
        wa_message_id=wa_message_id,
        debounce_token=token,
    )


def _dispatch_agent_q2(
    text_body: str,
    sender_phone: str,
    lead,
    wa_message_id: str = "",
    debounce_token: str = "",
) -> None:
    lead_id = getattr(lead, "id", None)

    try:
        from django_q.tasks import async_task
        task_id = async_task(
            "api.whatsapp.agent.handler.trigger_agent_response",
            incoming_body=text_body,
            sender_phone=sender_phone,
            lead_id=lead_id,
            wa_message_id=wa_message_id,
            debounce_token=debounce_token,
            q_options={
                "task_name": f"kemora_{sender_phone[-8:]}",
                "timeout":   120,
                "max_attempts": 1,
                "group": "kemora",
                "eta": _eta_from_now(AGENT_DEBOUNCE_SECONDS),
            },
        )
        logger.info(
            "Agent Kemora dépêché via Q2 | task_id=%s | phone=%s | lead_id=%s | delay=%ds",
            task_id, sender_phone, lead_id, AGENT_DEBOUNCE_SECONDS,
        )
    except Exception as exc:
        logger.error(
            "Django-Q2 indisponible — fallback synchrone | phone=%s | error=%s",
            sender_phone, exc,
        )
        try:
            from .agent.handler import trigger_agent_response
            trigger_agent_response(
                incoming_body=text_body,
                sender_phone=sender_phone,
                lead_id=lead_id,
                wa_message_id=wa_message_id,
                debounce_token="",
            )
        except Exception as exc2:
            logger.exception(
                "Fallback synchrone aussi échoué | phone=%s | error=%s", sender_phone, exc2,
            )


def _process_status_update(st: dict):
    wa_id        = st.get("id")
    status_value = st.get("status")

    if not wa_id or not status_value:
        return

    if status_value not in {"sent", "delivered", "read", "failed"}:
        return

    try:
        msg = WhatsAppMessage.objects.get(wa_id=wa_id)
        msg.delivery_status = status_value
        if status_value == "read":
            msg.is_read = True
        msg.save(update_fields=["delivery_status", "is_read"])
        logger.info("Statut sauvegardé | wa_id=%s | status=%s", wa_id, status_value)
    except WhatsAppMessage.DoesNotExist:
        logger.warning("Statut ignoré | message local introuvable pour wa_id=%s", wa_id)
    except Exception as exc:
        logger.exception("Échec sauvegarde statut | wa_id=%s | error=%s", wa_id, exc)


@never_cache
@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def whatsapp_webhook(request):
    if request.method == "GET":
        verify_token = getattr(settings, "WHATSAPP_VERIFY_TOKEN", "papex_secret_2026")
        mode      = request.GET.get("hub.mode")
        token     = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")

        if mode == "subscribe" and token == verify_token:
            logger.info("WhatsApp webhook vérifié")
            return HttpResponse(challenge, status=200)

        logger.warning("Échec vérification webhook WhatsApp | mode=%s | token=%s", mode, token)
        return HttpResponse("Forbidden", status=403)

    try:
        body = json.loads(request.body)

        for entry in body.get("entry", []):
            for change in entry.get("changes", []):
                value    = change.get("value", {})
                messages = value.get("messages", [])
                statuses = value.get("statuses", [])

                for msg in messages:
                    _process_incoming_message(msg)

                for st in statuses:
                    _process_status_update(st)

        return _no_cache(HttpResponse("EVENT_RECEIVED", status=200))

    except Exception as exc:
        logger.exception("Erreur Webhook WhatsApp : %s", exc)
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
        .prefetch_related(
            Prefetch(
                "whatsapp_messages",
                queryset=WhatsAppMessage.objects.order_by("-timestamp"),
            )
        )
        .select_related("whatsapp_settings")
        .distinct()
    )
    known = ConversationPreviewSerializer(leads, many=True).data

    unknown_phones_qs = (
        WhatsAppMessage.objects
        .filter(lead__isnull=True)
        .values("sender_phone")
        .annotate(last_msg_time=Max("timestamp"))
        .order_by("-last_msg_time")
    )
    unknown_phone_list = [e["sender_phone"] for e in unknown_phones_qs]

    if unknown_phone_list:
        all_unknown_messages = (
            WhatsAppMessage.objects
            .filter(lead__isnull=True, sender_phone__in=unknown_phone_list)
            .order_by("sender_phone", "-timestamp")
        )

        from collections import defaultdict
        msgs_by_phone: dict = defaultdict(list)
        for m in all_unknown_messages:
            msgs_by_phone[m.sender_phone].append(m)

        settings_qs = WhatsAppConversationSettings.objects.filter(
            lead__isnull=True, sender_phone__in=unknown_phone_list
        )
        agent_by_phone = {s.sender_phone: s.agent_enabled for s in settings_qs}

        unknown = []
        for phone in unknown_phone_list:
            phone_msgs = msgs_by_phone.get(phone, [])
            last_msg   = phone_msgs[0] if phone_msgs else None
            unread     = sum(1 for m in phone_msgs if not m.is_outbound and not m.is_read)
            agent_on   = agent_by_phone.get(phone, True)

            unknown.append({
                "id":           None,
                "sender_phone": phone,
                "first_name":   "Inconnu",
                "last_name":    phone,
                "phone":        phone,
                "last_message": WhatsAppMessageSerializer(last_msg).data if last_msg else None,
                "unread_count": unread,
                "is_unknown":   True,
                "agent_enabled": agent_on,
            })
    else:
        unknown = []

    def get_ts(conv):
        lm = conv.get("last_message")
        return lm["timestamp"] if lm and lm.get("timestamp") else ""

    all_conversations = sorted(list(known) + unknown, key=get_ts, reverse=True)

    logger.info(
        "Liste des conversations créée | connues=%d | inconnues=%d | total=%d",
        len(known), len(unknown), len(all_conversations),
    )

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
    messages = WhatsAppMessage.objects.filter(
        lead__isnull=True,
        sender_phone=phone,
    ).order_by("timestamp")
    return _no_cache(Response(WhatsAppMessageSerializer(messages, many=True).data))


@api_view(["POST"])
@permission_classes([AllowAny])
def send_message(request):
    serializer = SendMessageSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    lead_id = serializer.validated_data.get("lead_id")
    phone   = serializer.validated_data.get("phone")
    body    = serializer.validated_data["body"]

    lead = None
    if lead_id:
        try:
            lead     = Lead.objects.get(id=lead_id)
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
        logger.exception("Échec envoi WhatsApp via Meta | to=%s | error=%s", to_phone, exc)
        return Response(
            {"detail": "Échec envoi via Meta.", "error": str(exc)},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    wa_id   = meta_response.get("messages", [{}])[0].get("id", f"out_{to_phone}_{body[:8]}")
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


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def agent_settings_lead(request, lead_id: int):
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

    logger.info(
        "Toggle agent | lead_id=%s | agent_enabled=%s",
        lead_id, conv_settings.agent_enabled,
    )

    return Response({"agent_enabled": conv_settings.agent_enabled})


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def agent_settings_unknown(request, phone: str):
    conv_settings = WhatsAppConversationSettings.get_for_phone(phone)

    if request.method == "GET":
        return Response({"agent_enabled": conv_settings.agent_enabled})

    serializer = ToggleAgentSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    conv_settings.agent_enabled = serializer.validated_data["agent_enabled"]
    conv_settings.save(update_fields=["agent_enabled", "updated_at"])

    logger.info(
        "Toggle agent (inconnu) | phone=%s | agent_enabled=%s",
        phone, conv_settings.agent_enabled,
    )

    return Response({"agent_enabled": conv_settings.agent_enabled})