import ovh

# 🔐 Remplace par tes vraies clés
APP_KEY = "d388ddef898e1525"
APP_SECRET = "6e71c53653850baa57dd9560fe274be7"
CONSUMER_KEY = "6ef50e3c77eb7b50fd6989a7e87064ea"

SERVICE_SMS = "sms-ep141702-1"  # Remplace par ton service SMS OVH
NUMERO_DEST = "+33759650005"    # Numéro qui va recevoir le SMS

SENDER = "PAPEX"

# Création du client OVH
client = ovh.Client(
    endpoint="ovh-eu",
    application_key=APP_KEY,
    application_secret=APP_SECRET,
    consumer_key=CONSUMER_KEY,
)

try:
    # Vérifie la connexion
    info = client.get("/me")
    print("Connexion OK. Infos compte :", info)

    # Envoi du SMS
    result = client.post(
        f"/sms/{SERVICE_SMS}/jobs",
        sender=SENDER,
        message="Test SMS OVH via Python ✅",
        receivers=[NUMERO_DEST]
    )
    print("SMS envoyé ! Détails :", result)

except ovh.exceptions.BadParametersError as e:
    print("Paramètre incorrect :", e)
except ovh.exceptions.APIError as e:
    print("Erreur API :", e)
except Exception as e:
    print("Autre erreur :", e)
