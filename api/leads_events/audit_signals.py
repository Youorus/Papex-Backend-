import logging
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from django.db import transaction

from api.utils.context import get_current_user
from api.utils.audit import get_model_diff
from api.leads_events.models import LeadEvent

# Modèles à surveiller
from api.leads.models import Lead
from api.clients.models import Client
from api.comments.models import Comment
from api.contracts.models import Contract
from api.payments.models import PaymentReceipt
from api.leads_task.models import LeadTask

logger = logging.getLogger(__name__)

# Cache pour stocker l'état "avant"
_pre_save_cache = {}

@receiver(pre_save, sender=Lead)
@receiver(pre_save, sender=Client)
@receiver(pre_save, sender=Comment)
@receiver(pre_save, sender=Contract)
@receiver(pre_save, sender=PaymentReceipt)
@receiver(pre_save, sender=LeadTask)
def audit_pre_save(sender, instance, **kwargs):
    if instance.pk:
        try:
            _pre_save_cache[id(instance)] = sender.objects.get(pk=instance.pk)
        except sender.DoesNotExist:
            _pre_save_cache[id(instance)] = None
    else:
        _pre_save_cache[id(instance)] = None

@receiver(post_save, sender=Lead)
@receiver(post_save, sender=Client)
@receiver(post_save, sender=Comment)
@receiver(post_save, sender=Contract)
@receiver(post_save, sender=PaymentReceipt)
@receiver(post_save, sender=LeadTask)
def audit_post_save(sender, instance, created, **kwargs):
    old_instance = _pre_save_cache.pop(id(instance), None)
    actor = get_current_user()
    
    # On ignore si l'acteur n'est pas authentifié (optionnel selon le besoin)
    # Mais ici on veut aussi tracer les actions système (actor=None)
    
    lead = None
    event_code = ""
    data = {}

    # 1. Détermination du Lead racine et du code d'événement
    if isinstance(instance, Lead):
        lead = instance
        event_code = "LEAD_CREATED" if created else "LEAD_UPDATED"
    elif isinstance(instance, Client):
        lead = instance.lead
        event_code = "CLIENT_CREATED" if created else "CLIENT_UPDATED"
    elif isinstance(instance, Comment):
        lead = instance.lead
        event_code = "COMMENT_ADDED" if created else "COMMENT_UPDATED"
    elif isinstance(instance, Contract):
        lead = instance.client.lead
        event_code = "CONTRACT_GENERATED" if created else "CONTRACT_UPDATED"
    elif isinstance(instance, PaymentReceipt):
        lead = instance.client.lead
        event_code = "PAYMENT_RECEIVED" if created else "PAYMENT_UPDATED"
    elif isinstance(instance, LeadTask):
        lead = instance.lead
        event_code = "TASK_CREATED" if created else "TASK_UPDATED"

    if not lead:
        return

    # 2. Calcul du diff pour les mises à jour
    if not created:
        diff = get_model_diff(instance, old_instance)
        if not diff:
            return # Rien n'a changé d'important
        data["diff"] = diff

    # 3. Log de l'événement
    # On utilise transaction.on_commit pour être sûr que tout est synchrone avec la DB
    def log_event():
        try:
            LeadEvent.log(
                lead=lead,
                event_code=event_code,
                actor=actor if actor and actor.is_authenticated else None,
                data=data
            )
        except Exception as e:
            logger.error(f"Erreur lors de l'audit automatique ({event_code}): {e}")

    transaction.on_commit(log_event)


@receiver(post_delete, sender=Lead)
@receiver(post_delete, sender=Client)
@receiver(post_delete, sender=Comment)
@receiver(post_delete, sender=Contract)
@receiver(post_delete, sender=PaymentReceipt)
@receiver(post_delete, sender=LeadTask)
def audit_post_delete(sender, instance, **kwargs):
    actor = get_current_user()
    
    lead = None
    event_code = ""
    
    if isinstance(instance, Lead):
        # Pour un lead supprimé, on ne pourra plus l'afficher dans sa propre timeline après suppression physique,
        # mais on garde une trace système.
        lead = instance
        event_code = "LEAD_DELETED"
    elif isinstance(instance, Client):
        lead = instance.lead
        event_code = "CLIENT_DELETED"
    elif isinstance(instance, Comment):
        lead = instance.lead
        event_code = "COMMENT_DELETED"
    elif isinstance(instance, Contract):
        lead = instance.client.lead
        event_code = "CONTRACT_DELETED"
    elif isinstance(instance, PaymentReceipt):
        lead = instance.client.lead
        event_code = "PAYMENT_DELETED"
    elif isinstance(instance, LeadTask):
        lead = instance.lead
        event_code = "TASK_DELETED"

    if not lead or not lead.pk:
        # Si le lead parent est aussi en train d'être supprimé (CASCADE), 
        # on risque d'avoir des soucis d'intégrité si on essaie de logger.
        return

    try:
        LeadEvent.log(
            lead=lead,
            event_code=event_code,
            actor=actor if actor and actor.is_authenticated else None,
            data={"deleted_instance_repr": str(instance)}
        )
    except Exception as e:
        logger.error(f"Erreur lors de l'audit automatique de suppression ({event_code}): {e}")
