import os
import django
from django.utils import timezone
from openpyxl import Workbook

# 🔧 Initialisation Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "papex.settings.prod")
django.setup()

from api.clients.models import Client


def run():
    print("📤 Export des comptes ANEF en cours...")

    # Clients ayant au moins un contrat
    clients = (
        Client.objects
        .filter(contracts__isnull=False)
        .distinct()
        .select_related("lead")
    )

    wb = Workbook()
    ws = wb.active
    ws.title = "Comptes ANEF"

    # En-têtes Excel
    ws.append([
        "Nom",
        "Prénom",
        "Email ANEF",
        "Mot de passe ANEF",
        "Client ID",
        "Lead ID",
    ])

    count = 0

    for client in clients:
        if not client.anef_email and not client.anef_password:
            continue

        ws.append([
            client.lead.last_name,
            client.lead.first_name,
            client.anef_email or "",
            client.anef_password or "",
            client.id,
            client.lead.id,
        ])

        count += 1

    filename = f"export_anef_{timezone.now().strftime('%Y%m%d_%H%M')}.xlsx"
    wb.save(filename)

    print(f"✅ Export terminé : {count} client(s)")
    print(f"📄 Fichier généré : {filename}")


if __name__ == "__main__":
    run()
