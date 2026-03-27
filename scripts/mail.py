import os
import sys
import django
from django.conf import settings
from django.core.mail import send_mail

from dotenv import load_dotenv

# 1. Charger les variables d'environnement
print("--- 🔍 Debug: Chargement du .env ---")
load_dotenv()

# Vérification immédiate des variables critiques
host = os.getenv("EMAIL_HOST")
user = os.getenv("EMAIL_HOST_USER")
pwd = os.getenv("EMAIL_HOST_PASSWORD")

print(f"HOST récupéré: {host}")
print(f"USER récupéré: {user}")
print(f"PASSWORD récupéré: {'********' if pwd else 'VIDE'}")

if not host or not user or not pwd:
    print("❌ Erreur : Variables SMTP manquantes dans le .env")
    sys.exit(1)

# 2. Configurer Django de manière minimale
if not settings.configured:
    try:
        settings.configure(
            EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend',
            EMAIL_HOST=host,
            EMAIL_PORT=int(os.getenv("EMAIL_PORT", "587")),
            EMAIL_USE_TLS=os.getenv("EMAIL_USE_TLS", "true").lower() in ("true", "1"),
            EMAIL_HOST_USER=user,
            EMAIL_HOST_PASSWORD=pwd,
            DEFAULT_FROM_EMAIL=os.getenv("DEFAULT_FROM_EMAIL", user),
        )
        django.setup()
        print("✅ Django configuré pour le test.")
    except Exception as e:
        print(f"❌ Erreur lors de la configuration de Django : {e}")
        sys.exit(1)


def test_smtp_connection():
    subject = "🚀 Test SMTP Papex"
    message = "Si tu reçois cet email, c'est que la configuration SMTP fonctionne parfaitement !"
    recipient = user

    print(f"\n--- 🛰️ Tentative d'envoi via {settings.EMAIL_HOST}:{settings.EMAIL_PORT} ---")
    print(f"Utilisateur : {settings.EMAIL_HOST_USER}")
    print(f"Depuis: {settings.DEFAULT_FROM_EMAIL}")
    print(f"Vers: {recipient}")

    try:
        # On utilise le gestionnaire de connexion pour tester l'authentification explicitement
        from django.core.mail import get_connection
        connection = get_connection()
        print("Connexion au serveur SMTP...")
        connection.open()
        print("✅ Connexion établie et authentifiée !")

        print("Envoi de l'email de test...")
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [recipient],
            connection=connection,
            fail_silently=False,
        )
        connection.close()
        print("\n🎉 SUCCÈS ! L'email a été envoyé.")

    except Exception as e:
        print(f"\n❌ ERREUR SMTP :")
        print(f"Type: {type(e).__name__}")
        print(f"Message: {str(e)}")

        if "535" in str(e) or "authentication failed" in str(e).lower():
            print("\n👉 Diagnostic : Erreur d'authentification.")
            print(
                "Vérifiez que vous utilisez un 'Mot de passe d'application' (16 caractères) et non votre mot de passe Gmail habituel.")
        elif "timeout" in str(e).lower():
            print(
                "\n👉 Diagnostic : Connexion expirée. Vérifiez que votre réseau ou votre pare-feu autorise le port 587.")


if __name__ == "__main__":
    test_smtp_connection()