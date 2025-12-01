import os
import django
import csv

# ⚙️ Init Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tds.settings.prod")
django.setup()

from api.statut_dossier_interne.models import StatutDossierInterne

# 🎨 Palette de couleurs épurées et contrastées
PALETTE = [
    "#3b82f6",  # bleu
    "#10b981",  # vert émeraude
    "#f59e0b",  # orange
    "#8b5cf6",  # violet
    "#ec4899",  # rose
    "#14b8a6",  # turquoise
    "#f97316",  # orange foncé
    "#06b6d4",  # cyan
    "#84cc16",  # vert lime
    "#6366f1",  # indigo
    "#0ea5e9",  # bleu clair
    "#22c55e",  # vert moyen
]


def import_statuts(csv_file):
    with open(csv_file, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        for i, row in enumerate(reader):
            raw_code = row["code"].strip()
            raw_label = row["label"].strip()
            description = row.get("description", f"Statut interne : {raw_label}")
            # ⚡ Assigne une couleur unique en fonction de l'index
            color = PALETTE[i % len(PALETTE)]

            # Vérifier doublons
            if StatutDossierInterne.objects.filter(code=raw_code).exists():
                print(f"⏭️ Déjà existant : {raw_code}")
                continue

            # ⚠️ Prévisualisation
            print("\n--- Prévisualisation ---")
            print(f"Label       : {raw_label}")
            print(f"Code        : {raw_code}")
            print(f"Description : {description}")
            print(f"Couleur     : {color}")

            confirm = input("👉 Confirmer la création ? [Y/n] ").strip().lower()
            if confirm not in ("", "y", "yes"):
                print(f"⏭️ Ignoré : {raw_label}")
                continue

            # Création en base
            statut = StatutDossierInterne.objects.create(
                code=raw_code,
                label=raw_label,
                description=description,
                color=color,
            )
            print(f"✅ Créé : {statut.label} ({statut.code}) - {statut.color}")


if __name__ == "__main__":
    csv_path = "statuts_dossier_interne.csv"
    import_statuts(csv_path)