import os
import django

# ⚙️ Initialisation Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tds.settings.prod")
django.setup()

from django.db import transaction
from api.clients.models import Client
from api.contracts.models import Contract
from api.payments.models import PaymentReceipt
from api.leads.models import Lead

# 🔹 Entrer l'ID du client
CLIENT_ID = int(input("🧾 Entrez l'ID du client à supprimer : "))

try:
    client = Client.objects.select_related("lead").get(pk=CLIENT_ID)
except Client.DoesNotExist:
    print(f"❌ Aucun client trouvé avec l'ID {CLIENT_ID}")
    exit(1)

lead = client.lead
contracts = Contract.objects.filter(client=client)
payments = PaymentReceipt.objects.filter(contract__client=client)

print("\n📋 RÉSUMÉ AVANT SUPPRESSION")
print("─" * 80)
print(f"👤 Client : {client.id} | {lead.first_name} {lead.last_name} ({lead.email})")
print(f"📄 Contrats : {contracts.count()}")
print(f"💳 Paiements : {payments.count()}")
print(f"🎯 Lead : ID {lead.id}")
print("─" * 80)

confirm = input("⚠️ Confirmer la suppression complète de ce client et de toutes ses données ? (oui/non) : ").strip().lower()
if confirm not in ["oui", "o", "yes", "y"]:
    print("❌ Suppression annulée.")
    exit(0)

# 🔹 Suppression dans une transaction atomique
with transaction.atomic():
    deleted_payments, _ = payments.delete()
    deleted_contracts, _ = contracts.delete()
    deleted_client, _ = Client.objects.filter(pk=CLIENT_ID).delete()
    deleted_lead, _ = Lead.objects.filter(pk=lead.id).delete()

print("\n✅ Suppression terminée avec succès :")
print(f"🗑️ {deleted_contracts} contrat(s)")
print(f"🗑️ {deleted_payments} paiement(s)")
print(f"🗑️ 1 client")
print(f"🗑️ 1 lead associé")