from pathlib import Path

SIGN = {
    "FULL_NAME": "Marc Takoumba",
    "JOB_TITLE": "Responsable IT",
    "COMPANY_NAME": "Papiers-Express",
    "PHOTO_URL": "https://papiers-express.fr/icone.jpeg",
    "LOGO_URL": "https://papiers-express.fr/logo.png",
    "EMAIL": "marc.takoumba@papiers-express.fr",
    "WEBSITE": "https://papiers-express.fr",
    "INSTAGRAM": "https://instagram.com/papiers.express",
    "FACEBOOK": "https://facebook.com/papiers.express",
    "TIKTOK": "https://tiktok.com/@papiers.express",
    "ADDRESS_TEXT": "39 rue Navier, 75017 Paris, France",
    "ADDRESS_MAP": "39+rue+Navier,+75017+Paris,+France",

}

template = Path("/Users/marc./PycharmProjects/Papex-Backend/templates/signature/signature.html").read_text()

html = template
for k, v in SIGN.items():
    html = html.replace(f"{{{{{k}}}}}", v)

Path("signature_final.html").write_text(html)

print("Signature générée 👉 signature_final.html")