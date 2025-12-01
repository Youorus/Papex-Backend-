import pandas as pd
import phonenumbers
import math
import re
import unicodedata

file_path = "tds_data.xlsx"

# --- Étape 1 : détecter la ligne d’en-tête ---
preview = pd.read_excel(file_path, header=None, nrows=30)
header_row = None
for i, row in preview.iterrows():
    if row.astype(str).str.contains("Nom", case=False, na=False).any():
        header_row = i
        break

if header_row is None:
    raise ValueError("❌ Impossible de trouver la ligne contenant 'Nom'")

# --- Étape 2 : lecture avec en-tête ---
df = pd.read_excel(file_path, header=header_row)

# --- Normalisation des colonnes ---
def normalize_col(col: str) -> str:
    c = str(col).strip().lower()
    c = c.replace(" ", "_").replace("-", "_").replace("'", "_")
    return c

df.columns = [normalize_col(c) for c in df.columns]
print("✅ Colonnes normalisées :", list(df.columns))

# --- Mapping collaborateur -> ID ---
COLLAB_MAPPING = {
    "FRANCK NATAF": "06392a80-766f-4933-bbc0-e0e41614345c",
    "Marie": "9ddda9c1-0a4f-4eb8-a2d9-444af6d6e2e5",
    "PATRICK": "8d717fb9-84f2-4795-ba89-d820280fb5e5",
    "Michelle": "08292394-4a20-4304-bbeb-03acc601d2be",
    "ALLEY": "4cee7d46-0e66-4873-9e95-dabff7d9a9dc",
    "Cédric": "1ae06970-c3e4-48d1-b955-f88e9681ec7b",
    "TDS": "9d7147ff-e03f-4d31-ba47-6b083cd708c5",
}

# --- Fonction de normalisation des labels de service ---
def normalize_service_label(raw: str) -> str:
    if not raw or str(raw).lower() in ("nan", "none"):
        return ""
    s = "".join(
        c for c in unicodedata.normalize("NFD", str(raw))
        if unicodedata.category(c) != "Mn"
    )
    s = s.upper().strip()
    s = re.sub(r"\s+", " ", s)
    return s

# --- Charger services pour mapping ---
services_df = pd.read_csv(
    "services.csv"
)
SERVICE_MAPPING = {
    normalize_service_label(label): sid
    for label, sid in zip(services_df["label"], services_df["id"])
}

# --- Mapping mode de paiement ---
PAYMENT_MODE_MAPPING = {
    "CB": "CB",
    "CARTE": "CB",
    "CARTE BANCAIRE": "CB",
    "CHEQUE": "CHEQUE",
    "CHÈQUE": "CHEQUE",
    "ESPECES": "ESPECES",
    "ESPÈCES": "ESPECES",
    "VIREMENT": "VIREMENT",
    "VIRT BANCAIRE": "VIREMENT",
    "VRT BANCAIRE": "VIREMENT",
    "PAYPAL": "PAYPAL",
    "STRIPE": "STRIPE",
    "KLARNA": "KLARNA",
    "SCLP": "SCLP",  # Scalapay ?
    "PNF": "PNF",
    "4X PNF": "PNF",
    "4 FOIS PNF": "PNF",
}

def normalize_payment_mode(raw: str) -> str:
    if not raw or str(raw).lower() in ("nan", "none"):
        return ""
    raw = normalize_service_label(raw)  # supprime accents + uppercase
    return PAYMENT_MODE_MAPPING.get(raw, raw)

# --- Nettoyage téléphone ---
def clean_phone(raw):
    if pd.isna(raw):
        return ""
    if isinstance(raw, (float, int)) and not math.isnan(raw):
        raw = str(int(raw))
    else:
        raw = str(raw).strip()
    raw = raw.replace(" ", "").replace(".", "").replace(",", "")

    # Cas FR
    if raw.startswith("0"):
        return "+33" + raw[1:]
    if raw.startswith("33") and not raw.startswith("+"):
        return "+" + raw

    # Cas préfixes étrangers manquants
    if raw.startswith("359"):  # Bulgarie
        return "+" + raw
    if raw.startswith("93"):   # Afghanistan
        return "+" + raw

    # Cas FR sans 0 → ex: "620670550"
    if len(raw) == 9 and raw[0] in ["6", "7"]:
        return "+33" + raw

    if raw.startswith("+"):
        return raw

    return raw

def format_phone(raw):
    cleaned = clean_phone(raw)
    if not cleaned:
        return ""
    try:
        num = phonenumbers.parse(cleaned, None)  # ✅ None = auto-détection du pays par le préfixe
        if phonenumbers.is_valid_number(num):
            return phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)
        return ""
    except Exception:
        return ""

# --- Transformation ---
output = pd.DataFrame()
invalids = []
invalid_services = []

# Champs principaux
output["first_name"] = df.get("prenom", df.get("prénom", "")).astype(str).str.strip().str.capitalize()
output["last_name"] = df["nom"].astype(str).str.strip().str.capitalize()
output["email"] = df.get("email", df.get("e_mail", "")).astype(str).str.strip().str.lower()

# Téléphone
phones = []
for idx, raw in enumerate(df["telephone"]):
    formatted = format_phone(raw)
    if formatted:
        phones.append(formatted)
    else:
        phones.append("")
        invalids.append({
            "row": idx + 1,
            "name": f"{df.get('prenom', df.get('prénom', ''))[idx]} {df['nom'][idx]}",
            "email": df.get('email', df.get('e_mail', ''))[idx],
            "phone": raw,
            "reason": "Invalid after cleaning"
        })
output["phone"] = phones

output["created_at"] = pd.to_datetime(df.get("date_du_lead"), errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
output["appointment_date"] = pd.to_datetime(df.get("date_de_rdv"), errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")

# Collaborateur -> ID
output["collaborator_id"] = df["collaborateur"].astype(str).str.strip().map(COLLAB_MAPPING)

# Status par défaut
output["status_id"] = 4

# Contrat
output["contract_date"] = pd.to_datetime(df.get("date_du_contrat"), errors="coerce").dt.strftime("%Y-%m-%d")

# Service -> service_id
mapped_services = []
for idx, raw in enumerate(df["prestation_de_service"]):
    service_label = normalize_service_label(raw)
    sid = SERVICE_MAPPING.get(service_label)
    mapped_services.append(sid if sid else "")
    if not sid:
        invalid_services.append({
            "row": idx + 1,
            "raw_service": raw,
            "normalized": service_label,
            "reason": "Service not found in mapping"
        })
output["service_id"] = mapped_services

# Montant
output["montant"] = pd.to_numeric(df["total_ttc"], errors="coerce").fillna(0)

# Paiements
for i in range(1, 5):
    if i == 1:
        output[f"payment_{i}_amount"] = pd.to_numeric(df.get("acompte"), errors="coerce").fillna(0)
        output[f"payment_{i}_date"] = pd.to_datetime(df.get("date_de_l_acompte"), errors="coerce").dt.strftime("%Y-%m-%d")
        output[f"payment_{i}_method"] = df.get("acompte_methode_paiement", "").astype(str).map(normalize_payment_mode)
    else:
        output[f"payment_{i}_amount"] = pd.to_numeric(df.get(f"echeance_{i}_montant"), errors="coerce").fillna(0)
        output[f"payment_{i}_date"] = pd.to_datetime(df.get(f"echeance_{i}_date"), errors="coerce").dt.strftime("%Y-%m-%d")
        output[f"payment_{i}_method"] = df.get(f"echeance_{i}_methode_paiement", "").astype(str).map(normalize_payment_mode)

# Commentaires
output["commentaires"] = df.get("commentaires", "").astype(str).str.strip()

# --- Sauvegarde ---
output.to_csv("leads_with_contracts.csv", index=False, encoding="utf-8-sig")
print("✅ Nouveau CSV final généré avec collaborator_id, status_id, service_id et paiements normalisés")

if invalids:
    pd.DataFrame(invalids).to_csv("../structure/invalid_phones.csv", index=False, encoding="utf-8-sig")
    print(f"⚠️ {len(invalids)} téléphones invalides sauvegardés dans structure/invalid_phones.csv")
else:
    print("✅ Tous les téléphones sont valides")

if invalid_services:
    pd.DataFrame(invalid_services).to_csv("../structure/invalid_services.csv", index=False, encoding="utf-8-sig")
    print(f"⚠️ {len(invalid_services)} services non trouvés sauvegardés dans structure/invalid_services.csv")
else:
    print("✅ Tous les services correspondent au mapping")