import os
import django
from decimal import Decimal
import csv

# ⚙️ Initialisation Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tds.settings.prod")
django.setup()

from api.clients.models import Client
from api.contracts.models import Contract

# 🔹 Entrer l'ID du client
CLIENT_ID = 1635  # Remplace par l'ID réel

# 🔹 Nom du CSV de sortie
CSV_FILE = f"contracts_client_{CLIENT_ID}.csv"

try:
    client = Client.objects.get(pk=CLIENT_ID)
except Client.DoesNotExist:
    print(f"❌ Aucun client trouvé avec l'ID {CLIENT_ID}")
    exit(1)

# Récupérer tous les contrats du client
contracts = Contract.objects.filter(client=client).order_by("-created_at")

if not contracts.exists():
    print(f"⚠️ Aucun contrat trouvé pour le client {client.lead.first_name} {client.lead.last_name}")
    exit(0)

# Génération CSV
with open(CSV_FILE, mode="w", newline="", encoding="utf-8") as csvfile:
    writer = csv.writer(csvfile)
    # Ajouter l'ID du contrat dans l'en-tête
    writer.writerow([
        "Contract ID",
        "Date contrat",
        "Montant contrat (€)",
        "Montant payé (€)",
        "Solde restant (€)",
        "Contrat signé ?",
        "Contrat remboursé ?"
    ])

    for contract in contracts:
        writer.writerow([
            contract.id,  # ← ID du contrat
            contract.created_at.strftime("%Y-%m-%d"),
            f"{contract.amount_due:.2f}",
            f"{contract.amount_paid:.2f}",
            f"{contract.balance_due:.2f}",
            "Oui" if contract.is_signed else "Non",
            "Oui" if contract.is_refunded else "Non",
        ])

print(f"✅ CSV généré : {CSV_FILE}")