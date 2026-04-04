import os
import django

# 🔧 Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "papex.settings.prod")
django.setup()

from django.db import transaction

from api.users.models import User
from api.leads.models import Lead
from api.leads_task.models import LeadTask
from api.leads_task_type.models import LeadTaskType
from api.leads.constants import ABSENT


RAMA_EMAIL = "rama.haidara@papiers-express.fr"

print("\n🧹 ===== CLEAN ABSENT TASKS START =====\n")


# =========================================================
# 🔥 SETUP
# =========================================================

rama_user = User.objects.filter(email=RAMA_EMAIL).first()

if not rama_user:
    print("❌ Rama introuvable")
    raise SystemExit(1)

task_type = LeadTaskType.objects.filter(code="RELANCE_ABSENT").first()

if not task_type:
    print("❌ Task type RELANCE_ABSENT introuvable")
    raise SystemExit(1)


# =========================================================
# 🔥 LEADS ABSENTS
# =========================================================

leads = Lead.objects.filter(status__code=ABSENT)

print(f"📋 {leads.count()} leads ABSENTS détectés")


created = 0
deleted = 0


# =========================================================
# 🔥 CLEAN PAR LEAD
# =========================================================

with transaction.atomic():
    for lead in leads:

        tasks = LeadTask.objects.filter(
            lead=lead,
            task_type=task_type,
        ).order_by("created_at", "id")

        if not tasks.exists():
            continue

        # 👉 on garde la première
        first_task = tasks.first()

        # 🔥 si pas Rama → on réassigne
        if first_task.assigned_to != rama_user:
            first_task.assigned_to = rama_user
            first_task.save(update_fields=["assigned_to"])

        # 🔥 supprimer tout le reste
        to_delete = tasks.exclude(id=first_task.id)

        count = to_delete.count()

        if count:
            to_delete.delete()
            deleted += count

print(f"🔥 {deleted} tâches supprimées (doublons + mauvais users)")

print("\n✅ ===== CLEAN TERMINÉ =====\n")