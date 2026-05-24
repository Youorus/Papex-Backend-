import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "papex.settings.prod")
django.setup()

from django.db import transaction

from api.users.models import User


USER_EMAIL = "marc@papex.fr"
NEW_FIRST_NAME = "Marc"
NEW_LAST_NAME = "Takoumba"
NEW_PASSWORD = "Papex17075"


def main():
    try:
        user = User.objects.get(email=USER_EMAIL)
    except User.DoesNotExist:
        print(f"Utilisateur introuvable : {USER_EMAIL}")
        return

    print("\n=== RÉCAPITULATIF AVANT MISE À JOUR ===\n")
    print(f"Email : {user.email}")
    print(f"Prénom actuel : {user.first_name}")
    print(f"Nom actuel : {user.last_name}")
    print(f"Actif : {user.is_active}")
    print("\nNouvelles valeurs :")
    print(f"Prénom : {NEW_FIRST_NAME}")
    print(f"Nom : {NEW_LAST_NAME}")
    print("Mot de passe : ********")

    confirm = input("\nTape OUI pour confirmer la mise à jour : ")

    if confirm.strip() != "OUI":
        print("Opération annulée.")
        return

    with transaction.atomic():
        user.first_name = NEW_FIRST_NAME
        user.last_name = NEW_LAST_NAME
        user.set_password(NEW_PASSWORD)
        user.save()

    print(f"\n✅ Utilisateur mis à jour : {user.get_full_name()} <{user.email}>")


if __name__ == "__main__":
    main()