import ovh

# ==============================
# CONFIGURATION
# ==============================


import ovh


# ---------------------------------------------------------
# 1. CONFIGURATION (Remplissez avec vos NOUVELLES clés)
# ---------------------------------------------------------
APPLICATION_KEY = "80fe7b360276fb1f"
APPLICATION_SECRET = "9ebef196cdb67875d82e1cbdafa81ebe"
CONSUMER_KEY = "f7d4b1ccbdda2c9f01f7b7f79577e968"
# L'identifiant 'ep...' est généralement le Compte de Facturation (Billing Account)
BILLING_ACCOUNT = "ep141702-ovh-1"

# CORRECTION ICI : Remplacement du "+" par "00"
YOUR_SIP_LINE = "0033185099755"

# Pour le destinataire, le format +33 fonctionne généralement,
# mais si ça échoue, essayez aussi avec 0033...
DESTINATION_NUMBER = "+33759650005"

# ---------------------------------------------------------
# 2. INITIALISATION
# ---------------------------------------------------------
client = ovh.Client(
    endpoint="ovh-eu",
    application_key=APPLICATION_KEY,
    application_secret=APPLICATION_SECRET,
    consumer_key=CONSUMER_KEY
)

# ---------------------------------------------------------
# 3. APPEL
# ---------------------------------------------------------
try:
    print(f"📞 Tentative d'appel via la ligne {YOUR_SIP_LINE}...")

    # CORRECTION ICI : Le paramètre est 'calledNumber' et non 'called'
    response = client.post(
        f"/telephony/{BILLING_ACCOUNT}/line/{YOUR_SIP_LINE}/click2Call",
        calledNumber=DESTINATION_NUMBER
    )

    print("✅ Appel lancé avec succès !")
    print("Votre téléphone SIP (ou softphone) devrait sonner en premier.")
    print("Une fois décroché, il appellera le destinataire.")
    print(f"Réponse API : {response}")

except ovh.exceptions.APIError as e:
    print(f"\n❌ ERREUR OVH : {e}")
except Exception as e:
    print(f"\n❌ ERREUR : {e}")