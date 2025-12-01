import os
import django
import csv
import unicodedata
import re
from decimal import Decimal

# ⚙️ Init Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tds.settings.prod")
django.setup()

from api.services.models import Service


def slugify_code(text: str) -> str:
    """Transforme un label en code normalisé MAJ + underscore sans accents."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_")
    return text.upper()


def import_services(csv_file):
    with open(csv_file, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        for row in reader:
            label = row["label"].strip()
            price = Decimal(str(row["price"]).replace(",", "."))
            raw_code = row.get("code") or label
            code = slugify_code(raw_code)

            # Vérifier doublons
            if Service.objects.filter(code=code).exists():
                print(f"⏭️ Déjà existant : {code}")
                continue

            # Prévisualisation
            print("\n--- Prévisualisation ---")
            print(f"Code   : {code}")
            print(f"Label  : {label}")
            print(f"Prix   : {price} €")

            confirm = input("👉 Confirmer la création ? [Y/n] ").strip().lower()
            if confirm not in ("", "y", "yes"):
                print(f"⏭️ Ignoré : {label}")
                continue

            # Création en DB
            service = Service.objects.create(
                code=code,
                label=label,
                price=price,
            )
            print(f"✅ Créé : {service.label} ({service.code}) - {service.price} €")


if __name__ == "__main__":
    csv_path = "prestations_service_prix.csv"  # ⚠️ Mets ton chemin ici
    import_services(csv_path)