import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# --- 1. CONFIGURATION DES CHEMINS & DU .ENV ---
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))
load_dotenv(BASE_DIR / ".env")

# --- 2. INITIALISATION DE DJANGO (AVANT LES IMPORTS DJANGO !) ---
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'papex.settings.prod')
try:
    import django

    django.setup()
    print("✅ Django initialisé avec succès.")
except Exception as e:
    print(f"❌ Erreur d'initialisation de Django : {e}")
    sys.exit(1)

# --- 3. IMPORTS DJANGO (APRÈS L'INITIALISATION) ---
# 👇 C'est ici qu'on importe les modèles et les tâches ! 👇
from api.leads.models import Lead
from api.utils.email.leads.tasks import send_formulaire_task  # Ton chemin d'import mis à jour


def execute_email_dispatch():
    print("\n" + "=" * 50)
    print("🚀 DÉCLENCHEMENT MANUEL D'UNE TÂCHE EMAIL")
    print("=" * 50)

    # 👇 DÉFINIS L'ADRESSE DE RÉCEPTION ICI 👇
    TARGET_EMAIL = "ton.adresse.perso@gmail.com"

    lead = Lead.objects.first()

    if not lead:
        print("❌ ARRÊT : Aucun Lead trouvé dans la base de données.")
        sys.exit(1)

    original_email = lead.email
    print(f"👤 Lead ciblé      : #{lead.id} ({lead.first_name} {lead.last_name})")
    print(f"🎯 Email de destin : {TARGET_EMAIL}")
    print("-" * 50)

    try:
        # Substitution de l'email pour l'envoi
        lead.email = TARGET_EMAIL
        lead.save(update_fields=["email"])

        print("⏳ Envoi du formulaire en cours...")
        send_formulaire_task(lead.id)

        print(f"\n✅ OPÉRATION TERMINÉE : L'email a bien été expédié vers {TARGET_EMAIL}")

    except Exception as e:
        print(f"\n❌ ERREUR LORS DE L'ENVOI :")
        print(str(e))

    finally:
        # Restauration stricte
        lead.email = original_email
        lead.save(update_fields=["email"])
        print("🧹 Nettoyage : L'adresse email d'origine a été restaurée en DB.\n")


if __name__ == "__main__":
    execute_email_dispatch()