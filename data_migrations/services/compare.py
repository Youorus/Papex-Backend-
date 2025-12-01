import pandas as pd
import difflib
import re

# --- Paramètres ---
csv_django = "contracts_payments_2025_01.csv"  # export Django
csv_pdf = "contracts_cleaned.csv"  # export PDF
output_file = "comparaison_contrats_01_2025.csv"

# --- Lecture des fichiers ---
df_django = pd.read_csv(csv_django)
df_pdf = pd.read_csv(csv_pdf)


# --- Fonction de normalisation du numéro de téléphone ---
def normalize_phone(phone):
    if not isinstance(phone, str):
        phone = str(phone)
    phone = phone.strip()
    # Supprimer tout sauf les chiffres
    phone = re.sub(r"\D", "", phone)
    # Supprimer le préfixe 33 si présent
    if phone.startswith("33"):
        phone = phone[2:]
    # S'assurer que le numéro commence par 0
    if not phone.startswith("0"):
        phone = "0" + phone
    return phone


# --- Identifier la colonne Téléphone ---
def find_phone_column(df):
    for col in df.columns:
        if "téléphone" in col.lower() or "telephone" in col.lower() or "tel" in col.lower():
            return col
    raise ValueError("❌ Aucune colonne 'Téléphone' trouvée dans le CSV.")


# --- Normalisation des téléphones ---
col_tel_django = find_phone_column(df_django)
col_tel_pdf = find_phone_column(df_pdf)

df_django["Téléphone_normalisé"] = df_django[col_tel_django].apply(normalize_phone)
df_pdf["Téléphone_normalisé"] = df_pdf[col_tel_pdf].apply(normalize_phone)

# --- Comparaison directe sur les numéros ---
django_phones = set(df_django["Téléphone_normalisé"])
pdf_phones = set(df_pdf["Téléphone_normalisé"])

manquants_dans_pdf = sorted(list(django_phones - pdf_phones))
en_trop_dans_pdf = sorted(list(pdf_phones - django_phones))
communs = sorted(list(django_phones & pdf_phones))

# --- Correspondances floues (si numéros proches mais mal formatés) ---
flous = []
for tel_django in django_phones:
    match = difflib.get_close_matches(tel_django, pdf_phones, n=1, cutoff=0.8)
    if match and tel_django not in communs:
        flous.append({"Téléphone Django": tel_django, "Correspondance PDF": match[0]})

# --- Création du DataFrame résultat ---
result_df = pd.DataFrame({
    "Présents dans les deux (Téléphone)": pd.Series(communs),
    "Manquants dans PDF (Téléphone)": pd.Series(manquants_dans_pdf),
    "En trop dans PDF (Téléphone)": pd.Series(en_trop_dans_pdf)
})
result_df.to_csv(output_file, index=False, encoding="utf-8-sig")

# --- Export correspondances floues ---
if flous:
    pd.DataFrame(flous).to_csv("correspondances_floues.csv", index=False, encoding="utf-8-sig")
    print("🔎 Fichier 'correspondances_floues.csv' généré pour les correspondances approximatives.")

# --- Résumé ---
print("✅ Comparaison terminée.")
print(f"- Clients Django : {len(django_phones)}")
print(f"- Clients PDF : {len(pdf_phones)}")
print(f"- Commun(s) : {len(communs)}")
print(f"- Manquants dans PDF : {len(manquants_dans_pdf)}")
print(f"- En trop dans PDF : {len(en_trop_dans_pdf)}")
print(f"📄 Résultats enregistrés dans : {output_file}")
