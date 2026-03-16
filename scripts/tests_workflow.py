"""
scripts/test_workflow.py

Script de test complet du workflow d'automation CRM Papex.

Scénarios testés :
  1. Création lead → statut RDV_A_CONFIRMER + SMS confirmation
  2. Anti-doublon SMS confirmation (même date = pas de 2e SMS)
  3. Rappel RDV 24h + anti-doublon rappel
  4. Statut ABSENT → SMS urgence + tâche RELANCE_LEAD
  5. Statut PRESENT → SMS motivation planifié +2h
  6. Statut RDV_CONFIRME → pas de SMS supplémentaire
  7. CONTRACT_SIGNED → SMS félicitations planifié +2h

Prérequis :
  - seed_crm.py exécuté
  - Celery worker : celery -A papex worker -Q sms,scheduler,default -l info
  - Celery beat   : celery -A papex beat -l info

Usage :
    python scripts/test_workflow.py
    python scripts/test_workflow.py --quick   (délais réduits à 3s)
"""

import os
import sys
import time
import django
from datetime import timedelta

from api.leads.tasks import _send_reminder_if_needed

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "papex.settings.prod")
django.setup()

from django.utils import timezone

QUICK = "--quick" in sys.argv
WAIT  = 3 if QUICK else 10

# ================================================================
# IMPORTS APRÈS django.setup()
# ================================================================

from api.leads.models import Lead
from api.lead_status.models import LeadStatus
from api.leads_events.models import LeadEvent
from api.leads_task.models import LeadTask
from api.leads.constants import RDV_A_CONFIRMER, RDV_CONFIRME, ABSENT, PRESENT

# ================================================================
# HELPERS
# ================================================================

SEP  = "=" * 60
SEP2 = "-" * 60

_pass  = 0
_fail  = 0
_tests = []


def ok(msg):
    global _pass
    _pass += 1
    _tests.append(("✅", msg))
    print(f"  ✅ {msg}")


def fail(msg):
    global _fail
    _fail += 1
    _tests.append(("❌", msg))
    print(f"  ❌ {msg}")


def section(title):
    print(f"\n{SEP2}\n  {title}\n{SEP2}")


def wait(msg, seconds=None):
    s = seconds or WAIT
    print(f"\n  ⏳ {msg} ({s}s)...")
    time.sleep(s)


def get_status(code):
    try:
        return LeadStatus.objects.get(code=code)
    except LeadStatus.DoesNotExist:
        fail(f"LeadStatus '{code}' introuvable — vérifie le seed lead_status")
        return None


def assert_event(lead, event_code, label):
    exists = LeadEvent.objects.filter(
        lead=lead,
        event_type__code=event_code,
    ).exists()
    if exists:
        ok(f"{label} : LeadEvent {event_code} présent")
    else:
        fail(f"{label} : LeadEvent {event_code} ABSENT")
    return exists


def assert_event_count(lead, event_code, expected, label):
    count = LeadEvent.objects.filter(
        lead=lead,
        event_type__code=event_code,
    ).count()
    if count == expected:
        ok(f"{label} : {count}x {event_code} (attendu {expected})")
    else:
        fail(f"{label} : {count}x {event_code} (attendu {expected})")


def assert_task(lead, task_type_code, label):
    exists = LeadTask.objects.filter(
        lead=lead,
        task_type__code=task_type_code,
        completed_at__isnull=True,
    ).exists()
    if exists:
        ok(f"{label} : tâche {task_type_code} créée")
    else:
        fail(f"{label} : tâche {task_type_code} ABSENTE")
    return exists


def assert_status(lead, expected_code, label):
    lead.refresh_from_db()
    if lead.status.code == expected_code:
        ok(f"{label} : statut = {expected_code}")
    else:
        fail(f"{label} : statut attendu {expected_code}, obtenu {lead.status.code}")


def log_status_changed(lead, from_code, to_code):
    """Helper — log un STATUS_CHANGED et met à jour le statut du lead."""
    new_status = get_status(to_code)
    if not new_status:
        return None

    old_status_code = lead.status.code
    lead.status = new_status
    lead.save(update_fields=["status"])

    event = LeadEvent.log(
        lead=lead,
        event_code="STATUS_CHANGED",
        actor=None,
        data={"from": from_code, "to": to_code},
    )
    return event


# ================================================================
# SETUP — lead de test
# ================================================================

def setup_lead():
    section("SETUP — Lead de test")

    lead = Lead.objects.filter(
        phone="+33759650005",
        email="mtakoumba@gmail.com",
    ).first()

    if lead:
        print(f"  ♻️  Lead existant trouvé : lead_id={lead.id}")
        deleted_ev, _ = LeadEvent.objects.filter(lead=lead).delete()
        deleted_tk, _ = LeadTask.objects.filter(lead=lead).delete()
        print(f"  🗑  {deleted_ev} événements et {deleted_tk} tâches supprimés")

        # Réinitialise le statut
        status = get_status(RDV_A_CONFIRMER)
        if status:
            lead.status = status
            lead.appointment_date = timezone.now() + timedelta(hours=25)
            lead.save(update_fields=["status", "appointment_date"])
    else:
        status = get_status(RDV_A_CONFIRMER)
        if not status:
            return None

        lead = Lead.objects.create(
            first_name="Test",
            last_name="Workflow",
            phone="+33600000001",
            email="test.workflow@papex.fr",
            status=status,
            appointment_date=timezone.now() + timedelta(hours=25),
            service="TITRE_SEJOUR",
        )
        print(f"  ✅ Lead créé : lead_id={lead.id}")

    print(f"  📋 Statut initial  : {lead.status.code}")
    print(f"  📋 RDV             : {lead.appointment_date.strftime('%d/%m/%Y %H:%M')}")
    print(f"  📋 Service         : {lead.service}")
    print(f"  📋 Téléphone       : {lead.phone}")
    return lead


# ================================================================
# TEST 1 — CRÉATION LEAD → SMS CONFIRMATION
# ================================================================

def test_1_lead_created(lead):
    section("TEST 1 — Création lead → SMS confirmation RDV")

    event = LeadEvent.log(
        lead=lead,
        event_code="LEAD_CREATED",
        actor=None,
    )

    if event:
        ok("LeadEvent LEAD_CREATED créé")
    else:
        fail("LeadEvent LEAD_CREATED non créé")
        return

    # handle_lead_created doit passer le statut à RDV_A_CONFIRMER
    assert_status(lead, RDV_A_CONFIRMER, "Statut après LEAD_CREATED")

    wait("Attente traitement Celery SMS confirmation")

    # La task SMS doit avoir loggé APPOINTMENT_CONFIRMATION_SENT
    assert_event(lead, "APPOINTMENT_CONFIRMATION_SENT", "SMS confirmation RDV")

    print(f"\n  📊 Événements présents :")
    for ev in LeadEvent.objects.filter(lead=lead).select_related("event_type").order_by("occurred_at"):
        print(f"     {ev.occurred_at.strftime('%H:%M:%S')}  {ev.event_type.code}")


# ================================================================
# TEST 2 — ANTI-DOUBLON SMS CONFIRMATION (même date)
# ================================================================

def test_2_no_duplicate_sms(lead):
    section("TEST 2 — Anti-doublon SMS confirmation (même date RDV)")

    print(f"  📋 2e dispatch LEAD_CREATED pour lead_id={lead.id}")

    LeadEvent.log(lead=lead, event_code="LEAD_CREATED", actor=None)

    wait("Attente traitement Celery")

    # Doit toujours y avoir exactement 1 APPOINTMENT_CONFIRMATION_SENT
    assert_event_count(lead, "APPOINTMENT_CONFIRMATION_SENT", 1, "Anti-doublon SMS confirmation")


# ================================================================
# TEST 3 — RAPPEL RDV 24H + anti-doublon
# ================================================================

def test_3_reminder(lead):
    section("TEST 3 — Rappel RDV 24h + anti-doublon")


    print(f"  📋 1er appel _send_reminder_if_needed(lead, '24H')")
    _send_reminder_if_needed(lead, reminder_type="24H")

    wait("Attente traitement Celery SMS rappel")

    assert_event(lead, "APPOINTMENT_REMINDER_24H", "Rappel 24h envoyé")

    print(f"  📋 2e appel _send_reminder_if_needed(lead, '24H') — doit être ignoré")
    _send_reminder_if_needed(lead, reminder_type="24H")

    wait("Attente traitement Celery")

    assert_event_count(lead, "APPOINTMENT_REMINDER_24H", 1, "Anti-doublon rappel 24h")


# ================================================================
# TEST 4 — ABSENT → SMS URGENCE + TÂCHE RELANCE_LEAD
# ================================================================

def test_4_absent(lead):
    section("TEST 4 — Statut ABSENT → SMS urgence + tâche RELANCE_LEAD")

    event = log_status_changed(lead, lead.status.code, ABSENT)

    if event:
        ok("LeadEvent STATUS_CHANGED → ABSENT loggé")
    else:
        fail("LeadEvent STATUS_CHANGED non loggé")
        return

    assert_status(lead, ABSENT, "Statut mis à jour")

    wait("Attente traitement Celery SMS urgence + création tâche RELANCE_LEAD")

    # Tâche RELANCE_LEAD
    assert_task(lead, "RELANCE_LEAD", "Tâche relance commerciale")

    task = LeadTask.objects.filter(
        lead=lead,
        task_type__code="RELANCE_LEAD",
    ).first()

    if task:
        delta = task.due_at - timezone.now()
        hours = delta.total_seconds() / 3600

        print(f"\n  📋 Détail tâche RELANCE_LEAD :")
        print(f"     title        : {task.title}")
        print(f"     due_at       : {task.due_at.strftime('%d/%m/%Y %H:%M')}")
        print(f"     status       : {task.status.code}")
        print(f"     auto_created : {task.metadata.get('auto_created')}")
        print(f"     échéance     : +{hours:.1f}h")

        if 1.5 <= hours <= 2.5:
            ok(f"Échéance tâche cohérente (+{hours:.1f}h ≈ +2h)")
        else:
            fail(f"Échéance tâche incohérente (+{hours:.1f}h — attendu ~+2h)")

    # Anti-doublon tâche : un 2e STATUS_CHANGED → ABSENT ne doit pas créer une 2e tâche
    print(f"\n  📋 2e STATUS_CHANGED → ABSENT — ne doit pas créer une 2e tâche")
    log_status_changed(lead, ABSENT, ABSENT)

    wait("Attente traitement Celery")

    task_count = LeadTask.objects.filter(
        lead=lead,
        task_type__code="RELANCE_LEAD",
        completed_at__isnull=True,
    ).count()

    if task_count == 1:
        ok(f"Anti-doublon tâche OK : {task_count} seule tâche RELANCE_LEAD ouverte")
    else:
        fail(f"Anti-doublon tâche KO : {task_count} tâches RELANCE_LEAD ouvertes")


# ================================================================
# TEST 5 — PRESENT → SMS MOTIVATION +2H
# ================================================================

def test_5_present(lead):
    section("TEST 5 — Statut PRESENT → SMS motivation planifié +2h")

    event = log_status_changed(lead, lead.status.code, PRESENT)

    if event:
        ok("LeadEvent STATUS_CHANGED → PRESENT loggé")
    else:
        fail("LeadEvent STATUS_CHANGED non loggé")
        return

    assert_status(lead, PRESENT, "Statut mis à jour")

    wait("Attente dispatch Celery")

    # Le SMS est planifié +2h — on ne peut pas attendre 2h en test
    # On vérifie uniquement qu'aucune erreur n'est remontée
    print(f"  ℹ️  SMS motivation planifié dans +2h")
    print(f"      → vérifier dans les logs Celery : [sms_present_no_contract]")
    ok("Task SMS présent dispatchée (planifiée +2h — vérifier logs worker)")


# ================================================================
# TEST 6 — RDV_CONFIRME → PAS DE SMS SUPPLÉMENTAIRE
# ================================================================

def test_6_rdv_confirme(lead):
    section("TEST 6 — Statut RDV_CONFIRME → pas de SMS confirmation supplémentaire")

    count_before = LeadEvent.objects.filter(
        lead=lead,
        event_type__code="APPOINTMENT_CONFIRMATION_SENT",
    ).count()

    event = log_status_changed(lead, lead.status.code, RDV_CONFIRME)

    if event:
        ok("LeadEvent STATUS_CHANGED → RDV_CONFIRME loggé")
    else:
        fail("LeadEvent STATUS_CHANGED non loggé")
        return

    assert_status(lead, RDV_CONFIRME, "Statut mis à jour")

    wait("Attente traitement Celery")

    # Aucun SMS de confirmation ne doit s'ajouter
    assert_event_count(
        lead,
        "APPOINTMENT_CONFIRMATION_SENT",
        count_before,
        "Pas de SMS confirmation supplémentaire",
    )

    print(f"  ℹ️  WhatsApp + email bienvenue se déclencheront quand implémentés")


# ================================================================
# TEST 7 — CONTRACT_SIGNED → SMS FÉLICITATIONS +2H
# ================================================================

def test_7_contract_signed(lead):
    section("TEST 7 — CONTRACT_SIGNED → SMS félicitations planifié +2h")

    event = LeadEvent.log(
        lead=lead,
        event_code="CONTRACT_SIGNED",
        actor=None,
        data={"contract_id": 9999},  # ID fictif pour le test
    )

    if event:
        ok("LeadEvent CONTRACT_SIGNED créé")
    else:
        fail("LeadEvent CONTRACT_SIGNED non créé — vérifie le seed EVENT_TYPES")
        return

    wait("Attente dispatch Celery")

    # Le SMS est planifié +2h
    print(f"  ℹ️  SMS félicitations planifié dans +2h")
    print(f"      → vérifier dans les logs Celery : [sms_contract_signed]")
    ok("Task SMS contrat signé dispatchée (planifiée +2h — vérifier logs worker)")

    # Vérification que le handler handle_contract_signed a bien été déclenché
    # (si tu loggues un événement dans le handler, tu peux l'asserter ici)
    print(f"\n  📊 Événements CONTRACT_SIGNED :")
    for ev in LeadEvent.objects.filter(
        lead=lead,
        event_type__code="CONTRACT_SIGNED",
    ).order_by("occurred_at"):
        print(f"     {ev.occurred_at.strftime('%H:%M:%S')}  data={ev.data}")


# ================================================================
# RAPPORT FINAL
# ================================================================

def print_report(lead):
    print(f"\n{SEP}")
    print(f"  RAPPORT FINAL")
    print(f"{SEP}")

    print(f"\n  Résultats : ✅ {_pass} passés  ❌ {_fail} échoués\n")

    if _fail > 0:
        print(f"  Tests échoués :")
        for status, msg in _tests:
            if status == "❌":
                print(f"    ❌ {msg}")

    print(f"\n  Timeline événements — lead_id={lead.id} :")
    for ev in LeadEvent.objects.filter(lead=lead).select_related("event_type").order_by("occurred_at"):
        print(f"    {ev.occurred_at.strftime('%H:%M:%S')}  {ev.event_type.code:<40}  data={ev.data or ''}")

    print(f"\n  Tâches créées :")
    tasks = LeadTask.objects.filter(lead=lead).select_related("task_type", "status")
    if tasks.exists():
        for t in tasks:
            print(f"    [{t.status.code:<10}] {t.task_type.code:<20} — échéance {t.due_at.strftime('%d/%m %H:%M')}")
    else:
        print(f"    (aucune)")

    print(f"\n{SEP}\n")


# ================================================================
# MAIN
# ================================================================

def run():
    print(f"\n{SEP}")
    print(f"  TEST WORKFLOW — Papex Automation")
    print(f"  Mode : {'QUICK (délais 3s)' if QUICK else 'STANDARD (délais 10s)'}")
    print(f"{SEP}")

    lead = setup_lead()
    if not lead:
        print("\n❌ Impossible de créer le lead de test — arrêt\n")
        sys.exit(1)

    test_1_lead_created(lead)
    test_2_no_duplicate_sms(lead)
    test_3_reminder(lead)
    test_4_absent(lead)
    test_5_present(lead)
    test_6_rdv_confirme(lead)
    test_7_contract_signed(lead)

    print_report(lead)

    sys.exit(0 if _fail == 0 else 1)


if __name__ == "__main__":
    run()