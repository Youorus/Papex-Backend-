"""
api/leads/events/models.py

Audit trail du cycle de vie d'un lead.

Ce module fournit :
    - LeadEventType : types d'événements configurables
    - LeadEvent     : journal immuable des actions

Principe :
    ✔ aucune modification possible
    ✔ historique complet
    ✔ compatible automatisation / workflow
"""

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from api.leads_event_type.models import LeadEventType
from api.leads.automation.engine import AutomationEngine


class LeadEvent(models.Model):
    """
    Représente un événement dans l'historique d'un lead.

    Ce modèle sert d'audit trail pour tracer toutes les actions :
        - changement de statut
        - envoi email
        - modification d'un champ
        - création de tâche
        - etc.

    IMPORTANT :
        Un LeadEvent est IMMUTABLE.
        Une fois créé, il ne peut plus être modifié.

    Les données métier supplémentaires sont stockées dans `data`.
    """

    lead = models.ForeignKey(
        "leads.Lead",
        on_delete=models.CASCADE,
        related_name="events",
        verbose_name=_("lead"),
        help_text=_("Lead concerné par l'événement"),
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
        help_text=_("Utilisateur ayant déclenché l'événement"),
    )

    data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("données"),
        help_text=_(
            "Données contextuelles : "
            "valeurs avant/après, paramètres, etc."
        ),
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

    class Meta:
        verbose_name = _("événement lead")
        verbose_name_plural = _("événements lead")
        ordering = ["occurred_at"]
        indexes = [
            models.Index(fields=["lead", "occurred_at"]),
            models.Index(fields=["lead", "event_type"]),
            models.Index(fields=["actor"]),
        ]

    def __str__(self):
        actor = self.actor.get_full_name() if self.actor else "Système"
        return f"[{self.occurred_at:%d/%m/%Y %H:%M}] {self.event_type.label} — {actor}"

    # ─────────────────────────────────────
    # IMMUTABILITÉ
    # ─────────────────────────────────────

    def save(self, *args, **kwargs):
        """
        Empêche toute modification après création.
        """
        if self.pk:
            raise ValueError(
                "LeadEvent est immuable. "
                "Créez un nouvel événement pour corriger."
            )

        super().save(*args, **kwargs)

    # ─────────────────────────────────────
    # HELPER MÉTIER
    # ─────────────────────────────────────

    @classmethod
    def log(cls, lead, event_code, actor=None, data=None, note=""):
        """
        Helper rapide pour créer un événement ET déclencher les automatisations.

        Exemple :

            LeadEvent.log(
                lead=lead,
                event_code="STATUS_CHANGED",
                actor=request.user,
                data={"from": "NEW", "to": "RDV_CONFIRME"}
            )
        """

        # récupération type événement
        event_type, _ = LeadEventType.objects.get_or_create(
            code=event_code,
            defaults={
                "label": event_code.replace("_", " ").title()
            }
        )

        # création événement
        event = cls.objects.create(
            lead=lead,
            event_type=event_type,
            actor=actor,
            data=data or {},
            note=note,
        )

        # 🔥 déclenchement automatisations
        try:
            AutomationEngine.handle(event)
        except Exception as e:
            # on ne bloque jamais le système si l'automation échoue
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Erreur automation pour event {event_code}: {e}")

        return event