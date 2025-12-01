import os
import django

# ⚙️ Initialisation Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tds.settings.prod")
django.setup()

from api.contracts.models import Contract
from api.clients.models import Client

# 🔹 Entrer l'ID du client
CLIENT_ID = int(input("🧾 Entrez l'ID du client : "))

try:
    client = Client.objects.get(pk=CLIENT_ID)
except Client.DoesNotExist:
    print(f"❌ Aucun client trouvé avec l'ID {CLIENT_ID}")
    exit(1)

# 🔹 Récupérer tous les contrats du client
contracts = Contract.objects.filter(client=client).order_by("created_at")

if not contracts.exists():
    print(f"⚠️ Aucun contrat trouvé pour le client {client.lead.first_name} {client.lead.last_name}")
    exit(0)

print(f"\n📋 Contrats trouvés pour le client {client.lead.first_name} {client.lead.last_name} (ID={CLIENT_ID}) :")
print("─" * 80)
for c in contracts:
    print(
        f"ID: {c.id} | Date: {c.created_at:%Y-%m-%d} | Montant: {c.amount_due}€ | "
        f"Payé: {c.amount_paid}€ | Solde: {c.balance_due}€ | Signé: {'✅' if c.is_signed else '❌'}"
    )

# 🔹 Saisie des contrats à garder
to_keep_raw = input(
    "\n🛡️ Entrez les IDs des contrats à GARDER (séparés par des virgules) : "
).strip()

if not to_keep_raw:
    print("❌ Aucun ID saisi, opération annulée.")
    exit(0)

to_keep = {int(x.strip()) for x in to_keep_raw.split(",") if x.strip().isdigit()}

# 🔹 Identifier les contrats à supprimer
to_delete = [c for c in contracts if c.id not in to_keep]

if not to_delete:
    print("✅ Aucun contrat à supprimer.")
    exit(0)

print("\n⚠️ Les contrats suivants vont être SUPPRIMÉS :")
print("─" * 80)
for c in to_delete:
    print(f"🗑️ ID: {c.id} | Date: {c.created_at:%Y-%m-%d} | Montant: {c.amount_due}€")

# 🔹 Confirmation
confirm = input("\n❓ Confirmer la suppression ? (oui/non) : ").strip().lower()
if confirm not in ["oui", "o", "yes", "y"]:
    print("❌ Suppression annulée.")
    exit(0)

# 🔹 Suppression en base
deleted_count, _ = Contract.objects.filter(id__in=[c.id for c in to_delete]).delete()
print(f"✅ {deleted_count} contrats supprimés avec succès.")