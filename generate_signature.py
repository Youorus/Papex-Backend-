from pathlib import Path

SIGN = {
    "FULL_NAME": "Cédric Sakande",
    "JOB_TITLE": "Directeur général",
    "COMPANY_NAME": "Papiers-Express",
    "PHOTO_URL": "https://papiers-express.fr/icone.jpeg",
    "LOGO_URL": "https://papiers-express.fr/logo.png",
    "EMAIL": "cedric.sakande@papiers-express.fr",
    "WEBSITE": "https://papiers-express.fr",
    "INSTAGRAM": "https://instagram.com/papiers.express",
    "FACEBOOK": "https://www.facebook.com/profile.php?id=61585332640816",
    "TIKTOK": "https://tiktok.com/@papiers.express",
    "ADDRESS_TEXT": "39 rue Navier, 75017 Paris, France",
    "ADDRESS_MAP": "39+rue+Navier,+75017+Paris,+France",
    "PHONE1_RAW": "+33142596008",  # Premier numéro (format pour les liens tel: sans espaces)
    "PHONE1_DISPLAY": "+33 (0)1 42 59 60 08",  # Premier numéro (format d'affichage avec espaces)
    "PHONE2_RAW": "+33631018426",  # Deuxième numéro (format pour les liens tel: sans espaces)
    "PHONE2_DISPLAY": "06 31 01 84 26",  # Deuxième numéro (format d'affichage avec espaces)
}

template = Path("/Users/marc./PycharmProjects/Papex-Backend/templates/signature/signature.html").read_text()

html = template
for k, v in SIGN.items():
    html = html.replace(f"{{{{{k}}}}}", v)

Path("signature_final.html").write_text(html)

print("Signature générée 👉 signature_final.html")