import os
import django

# 🔧 Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "papex.settings.prod")
django.setup()

from django.db import transaction

from api.users.models import User
from api.leads_task.models import LeadTask


EMAIL = "test@papex.fr"

print(f"\n🧹 Suppression des tasks assignées à {EMAIL}...\n")

# 🔍 récupérer le user
user = User.objects.filter(email=EMAIL).first()

if not user:
    print("❌ Utilisateur introuvable")
    exit()

# 🔍 récupérer les tasks assignées à ce user
tasks = LeadTask.objects.filter(assigned_to=user)

count = tasks.count()

print(f"📋 {count} tâches trouvées")

if count == 0:
    print("✅ Rien à supprimer")
    exit()

# 🔥 suppression
with transaction.atomic():
    tasks.delete()

print(f"\n🔥 {count} tâches supprimées pour {EMAIL}\n")