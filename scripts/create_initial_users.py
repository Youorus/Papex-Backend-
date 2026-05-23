import os
import django
from getpass import getpass

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "papex.settings.prod")
django.setup()

from api.users.models import User
from api.users.roles import UserRoles


USERS_TO_CREATE = [
    {
        "first_name": "Perly",
        "last_name": "Mbokolo",
        "email": "perly.mbokolo@papiers-express.fr",
        "password": "Papex-Perly75",
        "role": UserRoles.JURISTE,
    },
    {
        "first_name": "Emma",
        "last_name": "Jacquin",
        "email": "emma.jacquin@papiers-express.fr",
        "password": "Papex-Emma75",
        "role": UserRoles.ACCUEIL,
    },
]


def main():
    print("\nUtilisateurs à créer :\n")

    for user in USERS_TO_CREATE:
        exists = User.objects.filter(email=user["email"]).exists()
        status = "EXISTE DÉJÀ" if exists else "À CRÉER"

        print(
            f"- {user['first_name']} {user['last_name']} | "
            f"{user['email']} | rôle: {user['role']} | {status}"
        )

    print("\nAttention : les mots de passe seront hashés par Django.")
    confirm = input("\nConfirmer la création ? Tape OUI pour continuer : ")

    if confirm.strip() != "OUI":
        print("Création annulée.")
        return

    for user in USERS_TO_CREATE:
        if User.objects.filter(email=user["email"]).exists():
            print(f"⚠️ Ignoré : {user['email']} existe déjà.")
            continue

        created_user = User.objects.create_user(
            email=user["email"],
            first_name=user["first_name"],
            last_name=user["last_name"],
            password=user["password"],
            role=user["role"],
        )

        print(
            f"✅ Créé : {created_user.email} "
            f"({created_user.get_full_name()}) - {created_user.role}"
        )

    print("\nTerminé.")


if __name__ == "__main__":
    main()