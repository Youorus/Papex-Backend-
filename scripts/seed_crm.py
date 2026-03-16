"""
scripts/seed_crm.py

Initialisation des données de référence nécessaires
au workflow d'automation CRM Papex.

Usage :
    python scripts/seed_crm.py

Options :
    --reset   Supprime les entrées existantes avant de recréer
              (ATTENTION : supprime aussi les LeadEvent/LeadTask liés)

Ce script crée uniquement ce dont l'automation a besoin.
Les types génériques (SUIVI_DOSSIER, NOTE_ADDED, etc.) sont
conservés mais clairement séparés des types critiques.
"""

import os
import sys
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "papex.settings.prod")
django.setup()

from api.leads_event_type.models import LeadEventType
from api.leads_task_type.models import LeadTaskType
from api.leads_task_status.models import LeadTaskStatus

RESET = "--reset" in sys.argv


# ================================================================
# LEAD EVENT TYPES
# ================================================================
#
# Seuls les types marqués [AUTO] sont utilisés par l'automation.
# Les autres sont utiles pour le CRM (logs manuels, UI) mais
# ne déclenchent pas de handler.
#
# [AUTO] = utilisé par AutomationEngine ou anti-doublon LeadEvent

EVENT_TYPES = [

    # ------ Cycle de vie lead ------
    ("LEAD_CREATED",                "Lead créé"),                   # [AUTO] → handle_lead_created
    ("STATUS_CHANGED",              "Changement de statut"),        # [AUTO] → handle_status_changed

    # ------ Confirmation RDV ------
    ("APPOINTMENT_CONFIRMATION_SENT", "SMS confirmation RDV envoyé"),  # [AUTO] anti-doublon SMS confirmation
    ("APPOINTMENT_REMINDER_24H",    "Rappel RDV 24h envoyé"),       # [AUTO] anti-doublon rappel 24h
    ("APPOINTMENT_REMINDER_48H",    "Rappel RDV 48h envoyé"),       # [AUTO] anti-doublon rappel 48h
    ("APPOINTMENT_MISSED",          "RDV manqué"),                  # [AUTO] loggé par mark_absent_leads

    ("CONTRACT_SIGNED", "Contrat signé")
    # ------ CRM manuel (non-automation) ------

]


# ================================================================
# LEAD TASK TYPES
# ================================================================
#
# [AUTO] = créé automatiquement par une task Celery

TASK_TYPES = [
    ("RELANCE_LEAD",    "Relance lead"),          # [AUTO] créé par create_absent_followup_task
    ("RAPPEL_RDV",      "Rappel rendez-vous"),
    ("SUIVI_DOSSIER",   "Suivi dossier"),
    ("ENVOI_DOCUMENT",  "Envoi document"),
    ("APPEL_SORTANT",   "Appel sortant"),
    ("CUSTOM",          "Tâche personnalisée"),
]


# ================================================================
# LEAD TASK STATUS
# ================================================================
#
# [AUTO] A_FAIRE est assigné à la création automatique des tâches

TASK_STATUSES = [
    ("A_FAIRE",      "À faire",    False),   # [AUTO] statut initial des tâches créées automatiquement
    ("EN_COURS",     "En cours",   False),
    ("FAIT",         "Faite",      True),
    ("ANNULEE",      "Annulée",    True),
    ("EN_RETARD",    "En retard",  False),
]


# ================================================================
# HELPERS
# ================================================================

def _reset_table(model, label):
    count, _ = model.objects.all().delete()
    print(f"  🗑  {count} {label} supprimés")


def _seed(model, items, fields_fn, label):
    print(f"\n--- {label} ---")
    created_count = 0
    for item in items:
        code = item[0]
        defaults = fields_fn(item)
        _, created = model.objects.update_or_create(
            code=code,
            defaults=defaults,
        )
        status = "✅ créé" if created else "↺  mis à jour"
        print(f"  {status} : {code}")
        if created:
            created_count += 1
    print(f"  → {created_count} créés / {len(items) - created_count} mis à jour")


# ================================================================
# SEED FUNCTIONS
# ================================================================

def seed_event_types():
    if RESET:
        _reset_table(LeadEventType, "LeadEventType")

    _seed(
        LeadEventType,
        EVENT_TYPES,
        lambda item: {
            "label":       item[1],
            "description": item[1],
            "is_system":   True,
        },
        "LeadEventType",
    )


def seed_task_types():
    if RESET:
        _reset_table(LeadTaskType, "LeadTaskType")

    _seed(
        LeadTaskType,
        TASK_TYPES,
        lambda item: {
            "label":       item[1],
            "description": item[1],
            "is_active":   True,
        },
        "LeadTaskType",
    )


def seed_task_statuses():
    if RESET:
        _reset_table(LeadTaskStatus, "LeadTaskStatus")

    _seed(
        LeadTaskStatus,
        TASK_STATUSES,
        lambda item: {
            "label":    item[1],
            "is_final": item[2],
        },
        "LeadTaskStatus",
    )


# ================================================================
# RUN
# ================================================================

def run():
    print("\n" + "=" * 55)
    print("  SEED CRM — Papex Automation")
    if RESET:
        print("  MODE : RESET (suppression + recréation)")
    else:
        print("  MODE : UPSERT (update_or_create)")
    print("=" * 55)

    seed_event_types()
    seed_task_types()
    seed_task_statuses()

    print("\n" + "=" * 55)
    print("  Seed terminé")
    print("=" * 55 + "\n")


if __name__ == "__main__":
    run()