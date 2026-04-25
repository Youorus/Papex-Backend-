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

AGENT_DEBOUNCE_SECONDS = getattr(settings, "KEMORA_DEBOUNCE_SECONDS", 4)

# Types ignorés : pas de réponse IA ni de sauvegarde
IGNORED_MESSAGE_TYPES = {"reaction", "unsupported"}

# Types média à sauvegarder avec leur représentation textuelle pour l'agent
MEDIA_TYPE_LABELS = {
    "image": "[Image]",
    "audio": "[Audio]",
    "video": "[Video]",
    "document": "[Document]",
    "sticker": "[Sticker]",
}


def _no_cache(response):
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    return response


def _parse_wa_timestamp(ts_value) -> "datetime":
    """Convertit le timestamp Unix Meta (int ou str) en datetime aware."""
    from django.utils import timezone
    import datetime

    try:
        ts = int(ts_value)
        return datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
    except (TypeError, ValueError, OSError):
        return timezone.now()


def _extract_message_data(msg: dict) -> dict:
    """
    Extrait toutes les données utiles d'un message WhatsApp entrant.

    Retourne un dict avec :
        body       : texte lisible (peut être [Image], [Audio], etc.)
        media_id   : ID Meta du média (si applicable)
        media_mime : MIME type (si disponible)
        media_caption : légende (si image/video avec caption)
        media_filename : nom du fichier (si document)
    """
    msg_type = msg.get("type", "text")

    # ── Texte simple ──────────────────────────────────────────────────────────
    if msg_type == "text":
        return {
            "body": msg.get("text", {}).get("body", ""),
            "media_id": None,
            "media_mime": None,
            "media_caption": None,
            "media_filename": None,
        }

    # ── Bouton interactif ─────────────────────────────────────────────────────
    if msg_type == "button":
        return {
            "body": msg.get("button", {}).get("text", ""),
            "media_id": None,
            "media_mime": None,
            "media_caption": None,
            "media_filename": None,
        }

    # ── Liste interactive ─────────────────────────────────────────────────────
    if msg_type == "interactive":
        interactive = msg.get("interactive", {})
        itype = interactive.get("type")
        if itype == "button_reply":
            body = interactive.get("button_reply", {}).get("title", "")
        elif itype == "list_reply":
            body = interactive.get("list_reply", {}).get("title", "")
        else:
            body = f"[Interactive: {itype}]"
        return {
            "body": body,
            "media_id": None,
            "media_mime": None,
            "media_caption": None,
            "media_filename": None,
        }

    # ── Image ─────────────────────────────────────────────────────────────────
    if msg_type == "image":
        img = msg.get("image", {})
        return {
            "body": "[Image]",
            "media_id": img.get("id"),
            "media_mime": img.get("mime_type", "image/jpeg"),
            "media_caption": img.get("caption") or None,
            "media_filename": None,
        }

    # ── Audio / Vocal ─────────────────────────────────────────────────────────
    if msg_type == "audio":
        audio = msg.get("audio", {})
        return {
            "body": "[Audio]",
            "media_id": audio.get("id"),
            "media_mime": audio.get("mime_type", "audio/ogg; codecs=opus"),
            "media_caption": None,
            "media_filename": None,
        }

    # ── Vidéo ─────────────────────────────────────────────────────────────────
    if msg_type == "video":
        vid = msg.get("video", {})
        return {
            "body": "[Video]",
            "media_id": vid.get("id"),
            "media_mime": vid.get("mime_type", "video/mp4"),
            "media_caption": vid.get("caption") or None,
            "media_filename": None,
        }

    # ── Document ──────────────────────────────────────────────────────────────
    if msg_type == "document":
        doc = msg.get("document", {})
        filename = doc.get("filename") or "document"
        return {
            "body": f"[Document: {filename}]",
            "media_id": doc.get("id"),
            "media_mime": doc.get("mime_type", "application/octet-stream"),
            "media_caption": doc.get("caption") or None,
            "media_filename": filename,
        }

    # ── Sticker ───────────────────────────────────────────────────────────────
    if msg_type == "sticker":
        sticker = msg.get("sticker", {})
        return {
            "body": "[Sticker]",
            "media_id": sticker.get("id"),
            "media_mime": sticker.get("mime_type", "image/webp"),
            "media_caption": None,
            "media_filename": None,
        }

    # ── Fallback ──────────────────────────────────────────────────────────────
    return {
        "body": f"[{msg_type}]",
        "media_id": None,
        "media_mime": None,
        "media_caption": None,
        "media_filename": None,
    }


def _process_incoming_message(msg: dict):
    wa_phone = msg.get("from", "")
    wa_id = msg.get("id", "")
    msg_type = msg.get("type", "unknown")
    wa_timestamp = msg.get("timestamp")

    logger.info(
        "Traitement du message WhatsApp entrant | wa_id=%s | from=%s | type=%s",
        wa_id, wa_phone, msg_type,
    )

    if msg_type in IGNORED_MESSAGE_TYPES:
        logger.info("Message ignoré (type non traitable) | wa_id=%s | type=%s", wa_id, msg_type)
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

    # Extraction des données du message (texte + média)
    extracted = _extract_message_data(msg)
    text_body = extracted["body"]
    real_timestamp = _parse_wa_timestamp(wa_timestamp)

    logger.info(
        "Résultat de la recherche de prospect | wa_phone=%s | lead_id=%s | body=%s",
        wa_phone, getattr(lead, "id", None), text_body[:60],
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
            timestamp=real_timestamp,
            # Médias
            media_id=extracted["media_id"],
            media_mime_type=extracted["media_mime"],
            media_caption=extracted["media_caption"],
            media_filename=extracted["media_filename"],
        )
        logger.info(
            "Message entrant enregistré | db_id=%s | wa_id=%s | lead_id=%s | type=%s",
            saved_message.id, wa_id, getattr(lead, "id", None), msg_type,
        )
    except Exception as exc:
        logger.exception(
            "Échec sauvegarde message WhatsApp entrant | wa_id=%s | error=%s", wa_id, exc,
        )
        return

    # Confirmation automatique de RDV via mot-clé
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
            logger.exception("Échec mise à jour statut lead | lead_id=%s | error=%s", lead.id, exc)

    # Vérification agent_enabled
    agent_active = WhatsAppConversationSettings.is_agent_enabled(lead=lead, phone=wa_phone)
    if not agent_active:
        logger.info(
            "Agent désactivé — pas de réponse automatique | phone=%s | lead_id=%s",
            wa_phone, getattr(lead, "id", None),
        )
        return

    _schedule_debounced_agent(
        text_body=text_body,
        sender_phone=wa_phone,
        lead=lead,
        wa_message_id=wa_id,
    )


# ─── Debounce ─────────────────────────────────────────────────────────────────

def _debounce_cache_key(sender_phone: str) -> str:
    return f"kemora_debounce_{sender_phone}"


def _eta_from_now(seconds: int):
    from django.utils import timezone
    import datetime
    return timezone.now() + datetime.timedelta(seconds=seconds)


def _schedule_debounced_agent(text_body, sender_phone, lead, wa_message_id):
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


def _dispatch_agent_q2(text_body, sender_phone, lead, wa_message_id="", debounce_token=""):
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
                "timeout": 120,
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
    wa_id = st.get("id")
    status_value = st.get("status")

    if not wa_id or not status_value:
        return

    if status_value not in {"sent", "delivered", "read", "failed"}:
        return

    try:
        msg_obj = WhatsAppMessage.objects.get(wa_id=wa_id)
        msg_obj.delivery_status = status_value
        if status_value == "read":
            msg_obj.is_read = True
        msg_obj.save(update_fields=["delivery_status", "is_read"])
        logger.info("Statut sauvegardé | wa_id=%s | status=%s", wa_id, status_value)
    except WhatsAppMessage.DoesNotExist:
        logger.warning("Statut ignoré | message local introuvable pour wa_id=%s", wa_id)
    except Exception as exc:
        logger.exception("Échec sauvegarde statut | wa_id=%s | error=%s", wa_id, exc)


# ─── Views ────────────────────────────────────────────────────────────────────

@never_cache
@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def whatsapp_webhook(request):
    if request.method == "GET":
        verify_token = getattr(settings, "WHATSAPP_VERIFY_TOKEN", "papex_secret_2026")
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")

        if mode == "subscribe" and token == verify_token:
            logger.info("WhatsApp webhook vérifié")
            return HttpResponse(challenge, status=200)

        logger.warning("Échec vérification webhook | mode=%s | token=%s", mode, token)
        return HttpResponse("Forbidden", status=403)

    try:
        body = json.loads(request.body)
        for entry in body.get("entry", []):
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
            last_msg = phone_msgs[0] if phone_msgs else None
            unread = sum(1 for m in phone_msgs if not m.is_outbound and not m.is_read)
            agent_on = agent_by_phone.get(phone, True)

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
        logger.exception("Échec envoi WhatsApp via Meta | to=%s | error=%s", to_phone, exc)
        return Response(
            {"detail": "Échec envoi via Meta.", "error": str(exc)},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    from django.utils import timezone
    wa_id = meta_response.get("messages", [{}])[0].get("id", f"out_{to_phone}_{body[:8]}")
    message = WhatsAppMessage.objects.create(
        wa_id=wa_id,
        lead=lead,
        sender_phone=to_phone,
        body=body,
        is_outbound=True,
        is_read=True,
        delivery_status="sent",
        timestamp=timezone.now(),
    )

    return Response(WhatsAppMessageSerializer(message).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([AllowAny])
def media_download(request, message_id: int):
    """
    Proxy de téléchargement de médias WhatsApp.

    GET /api/whatsapp/media/<message_id>/
    → Télécharge le fichier depuis Meta et le renvoie directement au navigateur.

    Pourquoi un proxy et pas juste l'URL Meta ?
    - Les URLs Meta sont bloquées par CORS (interdites directement depuis le navigateur).
    - Elles expirent en ~5 minutes.
    - Le navigateur ne peut pas envoyer le Bearer token Meta lui-même.
    """
    try:
        msg = WhatsAppMessage.objects.get(id=message_id)
    except WhatsAppMessage.DoesNotExist:
        from django.http import Http404
        raise Http404

    if not msg.media_id:
        return Response({"detail": "Ce message n\'a pas de média."}, status=status.HTTP_400_BAD_REQUEST)

    import requests as req
    from django.http import StreamingHttpResponse

    access_token = getattr(settings, "WHATSAPP_ACCESS_TOKEN", None)
    if not access_token:
        return Response(
            {"detail": "WHATSAPP_ACCESS_TOKEN manquant."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    auth_header = {"Authorization": f"Bearer {access_token}"}

    try:
        # Étape 1 : récupérer l'URL de téléchargement depuis l'API Meta Graph
        meta_info = req.get(
            f"https://graph.facebook.com/v25.0/{msg.media_id}",
            headers=auth_header,
            timeout=10,
        )
        meta_info.raise_for_status()
        download_url = meta_info.json().get("url")

        if not download_url:
            return Response(
                {"detail": "URL du média non disponible."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # Étape 2 : télécharger le binaire depuis Meta (streaming)
        media_resp = req.get(
            download_url,
            headers=auth_header,
            timeout=30,
            stream=True,
        )
        media_resp.raise_for_status()

        # Déterminer le content-type
        content_type = (
            msg.media_mime_type
            or media_resp.headers.get("Content-Type", "application/octet-stream")
        )

        # Nom de fichier pour le téléchargement (documents)
        filename = msg.media_filename or f"media_{message_id}"

        # Réponse streaming — on renvoie les chunks directement sans tout charger en RAM
        def stream_chunks():
            for chunk in media_resp.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk

        response = StreamingHttpResponse(
            stream_chunks(),
            content_type=content_type,
        )

        # Content-Disposition : inline pour images/audio/video, attachment pour documents
        is_inline = content_type.startswith(("image/", "audio/", "video/"))
        disposition = "inline" if is_inline else f'attachment; filename="{filename}"'
        response["Content-Disposition"] = disposition

        # CORS — autoriser le frontend à accéder au binaire
        response["Access-Control-Allow-Origin"] = "*"
        response["Cache-Control"] = "private, max-age=300"  # cache 5 min côté navigateur

        logger.info(
            "Média proxy OK | db_id=%s | media_id=%s | type=%s | inline=%s",
            message_id, msg.media_id, content_type, is_inline,
        )
        return response

    except req.HTTPError as exc:
        logger.error(
            "Erreur API Meta proxy média | media_id=%s | status=%s | error=%s",
            msg.media_id, exc.response.status_code if exc.response else "?", exc,
        )
        return Response(
            {"detail": "Erreur API Meta.", "error": str(exc)},
            status=status.HTTP_502_BAD_GATEWAY,
        )
    except Exception as exc:
        logger.exception(
            "Erreur inattendue proxy média | media_id=%s | error=%s",
            msg.media_id, exc,
        )
        return Response(
            {"detail": "Erreur serveur.", "error": str(exc)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


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

    logger.info("Toggle agent | lead_id=%s | agent_enabled=%s", lead_id, conv_settings.agent_enabled)
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

    logger.info("Toggle agent (inconnu) | phone=%s | agent_enabled=%s", phone, conv_settings.agent_enabled)
    return Response({"agent_enabled": conv_settings.agent_enabled})