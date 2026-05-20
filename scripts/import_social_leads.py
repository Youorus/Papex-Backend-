# scripts/import_social_leads.py

import csv
import os
import sys
from pathlib import Path

import django


# ==========================================================
# ⚙️ CONFIG DJANGO
# ==========================================================

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "papex.settings.prod")
django.setup()

from api.creators.models import SocialAccountLead  # noqa: E402


# ==========================================================
# 📁 CONFIG IMPORT
# ==========================================================

CSV_FILE = Path("/Users/marc./PycharmProjects/Papex-helper/influenceurs_ci.csv")


# ==========================================================
# 🧰 HELPERS
# ==========================================================

def clean_text(value) -> str:
    if value is None:
        return ""

    value = str(value).strip()

    if value.lower() in {"nan", "none", "null"}:
        return ""

    return value


def normalize_username(value) -> str:
    return clean_text(value).lstrip("@").strip()


def to_int(value) -> int:
    try:
        raw = clean_text(value).replace(",", "").replace(" ", "")

        if not raw:
            return 0

        upper = raw.upper()

        if upper.endswith("K"):
            return int(float(upper[:-1]) * 1_000)

        if upper.endswith("M"):
            return int(float(upper[:-1]) * 1_000_000)

        return int(float(raw))

    except (TypeError, ValueError):
        return 0


def normalize_raw_data(row: dict) -> dict:
    return {str(key): clean_text(value) for key, value in row.items()}


def build_notes(row: dict) -> str:
    notes_parts = []

    mapping = {
        "date_collecte": "Date de collecte",
        "followers_raw": "Followers brut",
        "likes": "Likes",
        "likes_raw": "Likes brut",
        "videos": "Nombre de vidéos",
        "region": "Région",
        "country_score": "Score pays",
        "source_videos": "Vidéos sources",
        "score_engagement": "Score engagement",
    }

    for key, label in mapping.items():
        value = clean_text(row.get(key))
        if value:
            notes_parts.append(f"{label} : {value}")

    return "\n".join(notes_parts)


# ==========================================================
# 🚀 IMPORT
# ==========================================================

def run() -> None:
    if not CSV_FILE.exists():
        print(f"❌ Fichier CSV introuvable : {CSV_FILE}")
        return

    print("🚀 Import des influenceurs Côte d’Ivoire")
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
                _, created = SocialAccountLead.objects.update_or_create(
                    platform=SocialAccountLead.Platform.TIKTOK,
                    username=username,
                    defaults={
                        "display_name": clean_text(row.get("nom")) or None,
                        "profile_url": clean_text(row.get("url")) or None,
                        "followers_count": to_int(row.get("followers")),
                        "bio": clean_text(row.get("bio")) or None,
                        "country": "Côte d'Ivoire",
                        "language": clean_text(row.get("langue")) or None,
                        "categories": (
                            clean_text(row.get("categories_detectees"))
                            or clean_text(row.get("source"))
                            or None
                        ),
                        "source": clean_text(row.get("source")) or "import_influenceurs_ci",
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