# scripts/import_social_leads.py

import csv
import os
import sys
from pathlib import Path

import django


BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "papex.settings.prod")
django.setup()

from api.creators.models import SocialAccountLead  # noqa: E402


CSV_FILE = Path("/Users/marc./PycharmProjects/Papex-helper/tiktok_ci_20260518_0956.csv")


def clean_text(value: str | None) -> str:
    return (value or "").strip()


def normalize_username(value: str | None) -> str:
    return clean_text(value).lstrip("@").strip()


def to_int(value) -> int:
    try:
        raw = str(value or "0").replace(",", "").replace(" ", "").strip()
        return int(float(raw))
    except (TypeError, ValueError):
        return 0


def normalize_raw_data(row: dict) -> dict:
    return {str(key): clean_text(value) for key, value in row.items()}


def build_notes(row: dict) -> str:
    notes_parts = []

    source = clean_text(row.get("sources"))
    if source:
        notes_parts.append(f"Source scraping : {source}")

    return "\n".join(notes_parts)


def run() -> None:
    if not CSV_FILE.exists():
        print(f"❌ Fichier CSV introuvable : {CSV_FILE}")
        return

    print("🚀 Import des comptes sociaux TikTok")
    print(f"📄 Fichier : {CSV_FILE}")

    created_count = 0
    updated_count = 0
    skipped_count = 0
    error_count = 0

    with CSV_FILE.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        for index, row in enumerate(reader, start=1):
            username = normalize_username(row.get("pseudo"))

            if not username:
                skipped_count += 1
                print(f"⏭️ Ligne {index} ignorée : pseudo vide")
                continue

            try:
                lead, created = SocialAccountLead.objects.update_or_create(
                    platform=SocialAccountLead.Platform.TIKTOK,
                    username=username,
                    defaults={
                        "display_name": clean_text(row.get("nom")) or None,
                        "profile_url": clean_text(row.get("url")) or None,
                        "followers_count": to_int(row.get("followers")),
                        "bio": clean_text(row.get("bio")) or None,
                        "country": clean_text(row.get("pays")) or None,
                        "language": clean_text(row.get("langue")) or None,
                        "categories": clean_text(row.get("categories")) or None,
                        "source": clean_text(row.get("sources")) or "import_csv",
                        "is_viable": True,
                        "contact_status": SocialAccountLead.ContactStatus.NEW,
                        "raw_data": normalize_raw_data(row),
                        "notes": build_notes(row) or None,
                    },
                )

                if created:
                    created_count += 1
                    print(f"🆕 Créé : @{username}")
                else:
                    updated_count += 1
                    print(f"♻️ Mis à jour : @{username}")

            except Exception as exc:
                error_count += 1
                print(f"❌ Erreur ligne {index} @{username} : {exc}")

    print("\n✅ Import terminé")
    print(f"🆕 Créés      : {created_count}")
    print(f"♻️ Mis à jour : {updated_count}")
    print(f"⏭️ Ignorés    : {skipped_count}")
    print(f"❌ Erreurs    : {error_count}")


if __name__ == "__main__":
    run()