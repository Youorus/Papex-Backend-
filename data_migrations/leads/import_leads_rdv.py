import os
import re
import django
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from unidecode import unidecode
from django.db.models import Q

# --- Init Django ---
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tds.settings.prod")  # adapte si besoin
django.setup()

from api.leads.models import Lead
from api.lead_status.models import LeadStatus

# --- Config ---
FILE_PATH = "/data_migrations/leads/tds_venir.csv"
PARIS_TZ = ZoneInfo("Europe/Paris")

# --- Étape 1 : vérifier fichier ---
if not os.path.exists(FILE_PATH):
    raise FileNotFoundError(f"❌ Fichier introuvable : {FILE_PATH}")
if os.path.getsize(FILE_PATH) == 0:
    raise ValueError(f"❌ Le fichier est vide : {FILE_PATH}")

# --- Étape 2 : chargement automatique selon l’extension ---
ext = os.path.splitext(FILE_PATH)[1].lower()
if ext == ".xlsx":
    preview = pd.read_excel(FILE_PATH, header=None, nrows=20, engine="openpyxl")
elif ext == ".csv":
    preview = pd.read_csv(FILE_PATH, header=None, nrows=20, sep=None, engine="python")
else:
    raise ValueError(f"❌ Format non supporté : {ext}")

# --- Étape 3 : détecter la ligne d'en-tête ---
header_row = None
for i, row in preview.iterrows():
    if row.astype(str).str.contains("Nom", case=False, na=False).any():
        header_row = i
        break

if header_row is None:
    raise ValueError("❌ Impossible de trouver la ligne contenant 'Nom'")

# --- Étape 4 : lecture complète avec la bonne ligne en header ---
if ext == ".xlsx":
    df = pd.read_excel(FILE_PATH, header=header_row, engine="openpyxl")
else:
    df = pd.read_csv(FILE_PATH, header=header_row, sep=None, engine="python")

# --- Étape 5 : normalisation colonnes ---
df.columns = [
    str(c).strip().lower()
    .replace(" ", "_")
    .replace("-", "_")
    .replace("é", "e")
    .replace("è", "e")
    .replace("ê", "e")
    .replace("à", "a")
    for c in df.columns
]

print("✅ Colonnes normalisées :", list(df.columns))

# --- Helper : trouver une colonne parmi plusieurs ---
def find_col(df, candidates):
    for c in df.columns:
        if c in candidates:
            return c
    raise KeyError(f"❌ Impossible de trouver une des colonnes : {candidates}")

# --- Colonnes clés ---
col_nom = find_col(df, ["nom"])
col_prenom = find_col(df, ["prenom"])
col_tel = find_col(df, ["telephone", "tel", "numero_de_telephone"])
col_email = find_col(df, ["e_mail", "email"])
col_conf = find_col(df, ["confirmation"])
col_statut_client = find_col(df, ["statut_client"])
col_date_rdv = find_col(df, ["date_de_rdv", "date_du_rdv"])
col_date_lead = find_col(df, ["date_du_lead", "lead_date"])

# --- Statut par défaut ---
try:
    default_status = LeadStatus.objects.get(code="RDV_PLANIFIE")
except LeadStatus.DoesNotExist:
    default_status = None

# --- Dates ---
now = datetime.now(PARIS_TZ)

def localize_to_paris(series):
    dt = pd.to_datetime(series, errors="coerce")
    if hasattr(dt.dt, "tz") and dt.dt.tz is not None:
        dt = dt.dt.tz_convert(PARIS_TZ)
    else:
        dt = dt.dt.tz_localize(PARIS_TZ, nonexistent="NaT", ambiguous="NaT")
    return dt

df[col_date_rdv] = localize_to_paris(df[col_date_rdv])
df[col_date_lead] = localize_to_paris(df[col_date_lead])

print(f"📅 Dates RDV min: {df[col_date_rdv].min()} / max: {df[col_date_rdv].max()}")

# --- Normalisation texte ---
df[col_statut_client] = (
    df[col_statut_client].astype(str).str.strip().apply(lambda x: unidecode(x).lower())
)
df[col_conf] = df[col_conf].astype(str).str.strip().apply(lambda x: unidecode(x).upper())

# --- Fonction de normalisation des téléphones ---
def normalize_phone_raw(value):
    """
    Nettoie et normalise un numéro de téléphone.
    Convertit +33 / 0033 / 33 en 0 et garde uniquement les chiffres.
    """
    if pd.isna(value):
        return ""
    s = str(value).strip()

    # Si float (ex: 33658637350.0)
    if re.match(r'^\d+\.0$', s):
        s = s.split('.')[0]

    # Supprimer tout sauf chiffres
    digits = re.sub(r'\D', '', s)
    if digits == "":
        return ""

    # Gérer formats internationaux français
    if digits.startswith("00") and digits[2:4] == "33":
        digits = "0" + digits[4:]
    elif digits.startswith("33") and len(digits) >= 11:
        digits = "0" + digits[2:]
    elif digits.startswith("336") and len(digits) == 11:
        digits = "0" + digits[3:]

    return digits

# --- Appliquer la normalisation téléphone ---
df[col_tel] = df[col_tel].apply(normalize_phone_raw)
print("📞 Aperçu des téléphones normalisés :", df[col_tel].dropna().astype(str).unique()[:10])

# --- Filtre : uniquement par statut et RDV non vide ---
df_filtered = df[
    (df[col_statut_client].isin(["rdv valide", "rdv confirme"])) &
    (df[col_date_rdv].notna())
]

print(f"📌 {len(df_filtered)} leads valides trouvés (toutes dates confondues)")

# --- Préparation des leads ---
leads_to_create = []
for _, row in df_filtered.iterrows():
    statut_client = row[col_statut_client]
    confirmation = row[col_conf]
    rdv_date = row[col_date_rdv]

    status = default_status
    if statut_client == "rdv confirme" and confirmation == "OK" and pd.notna(rdv_date):
        status = LeadStatus.objects.filter(code__iexact="RDV_CONFIRME").first()
    elif statut_client == "rdv valide" and pd.notna(rdv_date):
        status = LeadStatus.objects.filter(code__iexact="RDV_PLANIFIE").first()

    if not status:
        print(f"⚠️ Pas de statut trouvé pour: statut_client={statut_client}, confirmation={confirmation}")

    leads_to_create.append({
        "first_name": str(row.get(col_prenom, "")).capitalize(),
        "last_name": str(row.get(col_nom, "")).capitalize(),
        "email": str(row.get(col_email, None)).strip() or None,
        "phone": normalize_phone_raw(row.get(col_tel, "")),
        "appointment_date": rdv_date,
        "created_at": row[col_date_lead] if pd.notna(row[col_date_lead]) else now,
        "status": status,
    })

# --- Aperçu ---
print("\n📌 Exemple des 5 premiers leads :")
for lead in leads_to_create[:5]:
    print(f"- {lead['first_name']} {lead['last_name']} | Statut={lead['status'].code if lead['status'] else '??'} | RDV={lead['appointment_date']}")

# --- Confirmation ---
confirm = input("\n👉 Voulez-vous insérer tous ces leads en base ? (o/n) : ")

if confirm.lower() == "o":
    inserted = 0
    skipped = 0

    for lead in leads_to_create:
        phone = normalize_phone_raw(lead.get("phone", ""))

        if not phone:
            print(f"⚠️ Lead sans numéro : {lead['first_name']} {lead['last_name']} → Ignoré.")
            skipped += 1
            continue

        existing = Lead.objects.filter(phone__iexact=phone).first()

        if existing:
            print(f"⚠️ Lead déjà existant : {existing.first_name} {existing.last_name} "
                  f"({existing.phone}) → Ignoré.")
            skipped += 1
            continue

        lead["phone"] = phone
        created_lead = Lead.objects.create(**lead)
        print(f"✅ Lead inséré : {created_lead.first_name} {created_lead.last_name} "
              f"| Statut={created_lead.status.code if created_lead.status else '??'} "
              f"| RDV={created_lead.appointment_date}")
        inserted += 1

    print(f"\n🎉 {inserted} leads insérés, {skipped} doublons ignorés.")
else:
    print("❌ Insertion annulée.")
