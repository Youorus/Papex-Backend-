import logging
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from api.comments.models import Comment
from api.comments.serializers import CommentSerializer
from api.websocket.signals.base import broadcast, safe_payload

logger = logging.getLogger(__name__)

def _send_comment_event(event: str, instance: Comment):
    payload = safe_payload(event, instance, CommentSerializer)
    
    # On notifie le groupe général des leads et le groupe spécifique au lead du commentaire
    groups = ["leads", f"leads_{instance.lead_id}"]
    
    transaction.on_commit(lambda: broadcast(groups, payload))

@receiver(post_save, sender=Comment)
def on_comment_saved(sender, instance: Comment, created, **kwargs):
    logger.info("💬 post_save Comment id=%s (created=%s)", instance.id, created)
    _send_comment_event("created" if created else "updated", instance)

@receiver(post_delete, sender=Comment)
def on_comment_deleted(sender, instance: Comment, **kwargs):
    logger.info("💬 post_delete Comment id=%s", instance.id)
    _send_comment_event("deleted", instance)
