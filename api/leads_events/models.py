"""
api/leads/events/models.py

Audit trail immuable du cycle de vie d'un lead, structuré en arbre.

Enrichissements :
    - parent_event  : FK self → permet de construire un arbre de causalité
    - attachments   : M2M → Document (pièces jointes à l'événement)
    - position_x/y  : coordonnées pour le canvas interactif (React Flow)
"""

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from api.leads_event_type.models import LeadEventType
from api.leads.automation.engine import AutomationEngine


class LeadEvent(models.Model):
    """
    Représente un événement dans l'historique d'un lead.

    Structure en arbre :
        Un événement peut avoir un parent (parent_event).
        Cela permet de modéliser des chaînes causales :
            "Éligibilité confirmée"
                └── "Dossier transmis au juriste"
                        └── "Document CERFA envoyé"
                        └── "Accusé de réception reçu"

    IMPORTANT : Un LeadEvent est IMMUTABLE une fois créé.
    Exception : position_x / position_y (UI uniquement, pas de données métier).
    """

    lead = models.ForeignKey(
        "leads.Lead",
        on_delete=models.CASCADE,
        related_name="events",
        verbose_name=_("lead"),
    )

    event_type = models.ForeignKey(
        LeadEventType,
        on_delete=models.PROTECT,
        related_name="events",
        verbose_name=_("type d'événement"),
    )

    actor = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lead_events",
        verbose_name=_("acteur"),
    )

    # 🌳 Arbre
    parent_event = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
        verbose_name=_("événement parent"),
        help_text=_("Événement parent dans l'arbre du cycle de vie"),
    )

    # 📎 Documents liés
    attachments = models.ManyToManyField(
        "documents.Document",
        blank=True,
        related_name="events",
        verbose_name=_("documents liés"),
    )

    data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("données"),
    )

    note = models.TextField(
        blank=True,
        verbose_name=_("note"),
    )

    occurred_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        verbose_name=_("date de l'événement"),
    )

    # 🎨 Position canvas React Flow (mutable — UI uniquement)
    position_x = models.FloatField(
        default=0.0,
        verbose_name=_("position X"),
    )
    position_y = models.FloatField(
        default=0.0,
        verbose_name=_("position Y"),
    )

    class Meta:
        verbose_name = _("événement lead")
        verbose_name_plural = _("événements lead")
        ordering = ["occurred_at"]
        indexes = [
            models.Index(fields=["lead", "occurred_at"]),
            models.Index(fields=["lead", "event_type"]),
            models.Index(fields=["lead", "parent_event"]),
            models.Index(fields=["actor"]),
        ]

    def __str__(self):
        actor = self.actor.get_full_name() if self.actor else "Système"
        return f"[{self.occurred_at:%d/%m/%Y %H:%M}] {self.event_type.label} — {actor}"

    # ─────────────────────────────────────
    # IMMUTABILITÉ (sauf position UI)
    # ─────────────────────────────────────

    MUTABLE_FIELDS = {"position_x", "position_y"}

    def save(self, *args, **kwargs):
        """
        Empêche toute modification métier après création.
        Autorise uniquement la mise à jour des positions UI.
        """
        if self.pk:
            update_fields = kwargs.get("update_fields", set())
            if update_fields and set(update_fields).issubset(self.MUTABLE_FIELDS):
                # ✅ Mise à jour position uniquement → autorisée
                return super().save(*args, **kwargs)
            raise ValueError(
                "LeadEvent est immuable. "
                "Créez un nouvel événement ou utilisez update_fields=['position_x','position_y']."
            )
        super().save(*args, **kwargs)

    # ─────────────────────────────────────
    # HELPER MÉTIER
    # ─────────────────────────────────────

    @classmethod
    def log(cls, lead, event_code, actor=None, data=None, note="",
            parent_event=None, attachment_ids=None):
        """
        Crée un événement, attache des documents, déclenche les automatisations.

        Exemple :
            LeadEvent.log(
                lead=lead,
                event_code="DOCUMENT_SENT",
                actor=request.user,
                data={"document": "CERFA_15011"},
                parent_event=eligibility_event,
                attachment_ids=[42, 43],
            )
        """
        event_type, _ = LeadEventType.objects.get_or_create(
            code=event_code,
            defaults={"label": event_code.replace("_", " ").title()},
        )

        event = cls.objects.create(
            lead=lead,
            event_type=event_type,
            actor=actor,
            data=data or {},
            note=note,
            parent_event=parent_event,
        )

        if attachment_ids:
            from api.documents.models import Document
            docs = Document.objects.filter(pk__in=attachment_ids, client=lead.form_data)
            event.attachments.set(docs)

        try:
            AutomationEngine.handle(event)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Erreur automation pour event {event_code}: {e}")

        return event