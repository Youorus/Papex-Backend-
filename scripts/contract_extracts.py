import os
import django
from django.utils import timezone
from openpyxl import Workbook

# 🔧 Initialisation Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "papex.settings.prod")
django.setup()

from api.contracts.models import Contract


def run():
    print("🔎 Recherche des contrats sans acompte...")

    # Contrats sans aucun reçu de paiement
    contracts = (
        Contract.objects
        .filter(receipts__isnull=True)
        .select_related("client", "service", "created_by")
    )

    wb = Workbook()
    ws = wb.active
    ws.title = "Contrats sans acompte"

    ws.append([
        "Contract ID",
        "Client",
        "Service",
        "Montant",
        "Montant réel",
        "Créé le",
        "Créé par",
    ])

    count = 0

    for contract in contracts:
        ws.append([
            contract.id,
            getattr(contract.client, "full_name", contract.client.id),
            contract.service.name if contract.service else "",
            float(contract.amount_due),
            float(contract.real_amount),
            contract.created_at.strftime("%Y-%m-%d"),
            str(contract.created_by) if contract.created_by else "",
        ])

        count += 1

    filename = f"contracts_sans_acompte_{timezone.now().strftime('%Y%m%d_%H%M')}.xlsx"
    wb.save(filename)

    print(f"✅ {count} contrat(s) trouvé(s)")
    print(f"📄 Fichier généré : {filename}")


if __name__ == "__main__":
    run()