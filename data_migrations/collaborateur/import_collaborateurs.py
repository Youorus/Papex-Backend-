import os
import django
import csv
import unicodedata

# ⚙️ Initialisation Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tds.settings.prod")
django.setup()

from api.users.models import User


def strip_accents(text: str) -> str:
    """Supprime les accents et caractères spéciaux d'une chaîne."""
    return ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )


def ask_role(collaborateur):
    """
    Menu interactif pour choisir un rôle pour un collaborateur donné.
    """
    roles = ["ADMIN", "ACCUEIL", "JURISTE", "CONSEILLER"]
    print(f"\n👉 Collaborateur : {collaborateur}")
    print("Choisissez un rôle :")
    for i, r in enumerate(roles, 1):
        print(f"{i}. {r}")
    while True:
        try:
            choice = int(input("Votre choix : "))
            if 1 <= choice <= len(roles):
                return roles[choice - 1]
        except ValueError:
            pass
        print("❌ Choix invalide, réessayez.")


def import_collaborateurs(csv_file):
    """
    Lecture d'un fichier CSV et création des utilisateurs.
    """
    with open(csv_file, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)

        # ⚠️ Sauter l'en-tête
        header = next(reader, None)

        for row in reader:
            if not row:
                continue

            first_name = row[0].strip().capitalize()
            last_name = ""  # ton CSV n’a qu’un prénom

            # 🔥 Supprimer les accents dans l'email
            email_local = strip_accents(first_name.lower())
            email = f"{email_local}@tds.fr"

            # Vérifier si l'utilisateur existe déjà
            if User.objects.filter(email=email).exists():
                print(f"⏭️ Déjà existant : {email}")
                continue

            print(f"\nCréation de l'utilisateur : {first_name}")

            # Demander le rôle en affichant le collaborateur
            role_value = ask_role(first_name)

            # Mot de passe basé sur la règle : <Role><Initial>@tds1
            password = f"{role_value.capitalize()}{first_name[0].upper()}@tds1"

            # Résumé + confirmation
            print("\nRésumé utilisateur :")
            print(f"  Nom complet : {first_name} {last_name}")
            print(f"  Email      : {email}")
            print(f"  Rôle       : {role_value}")
            print(f"  Mot de passe provisoire : {password}")

            confirm = input("Confirmer la création ? [Y/n] ").strip().lower()
            if confirm not in ("", "y", "yes"):
                print(f"⏭️ Ignoré : {first_name}")
                continue

            # Création utilisateur
            user = User.objects.create_user(
                email=email,
                first_name=first_name,
                last_name=last_name,
                password=password,
                role=role_value,
            )
            print(f"✅ Créé : {user.get_full_name()} [{role_value}] ({email})")


if __name__ == "__main__":
    # ⚠️ Mets ton vrai chemin CSV ici
    csv_path = "collaborateurs.csv"
    import_collaborateurs(csv_path)