import os
import django
import csv
from decimal import Decimal
from datetime import datetime

# ⚙️ 1️⃣ Initialiser Django AVANT d'importer les modèles
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tds.settings.prod")
django.setup()

# 2️⃣ Importer ensuite les modèles
from api.clients.models import Client
from api.contracts.models import Contract
from api.payments.models import PaymentReceipt

# 3️⃣ Paramètres : mois et année à filtrer
YEAR = 2025
MONTH = 1
CSV_FILE = f"contracts_payments_{YEAR}_{MONTH:02d}.csv"

with open(CSV_FILE, mode="w", newline="", encoding="utf-8") as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(["Nom", "Prénom", "Téléphone", "Date contrat", "Montant contrat (€)", "Paiements (€)"])

    contracts = Contract.objects.filter(
        created_at__year=YEAR,
        created_at__month=MONTH
    ).select_related("client__lead")

    for contract in contracts:
        client = contract.client
        payments = PaymentReceipt.objects.filter(
            contract=contract,
            payment_date__year=YEAR,
            payment_date__month=MONTH
        )
        total_payments = sum(p.amount for p in payments) if payments.exists() else Decimal("0.00")

        writer.writerow([
            client.lead.last_name,
            client.lead.first_name,
            client.lead.phone,
            contract.created_at.strftime("%Y-%m-%d"),
            f"{contract.amount_due:.2f}",
            f"{total_payments:.2f}"
        ])

print(f"✅ CSV généré : {CSV_FILE}")
