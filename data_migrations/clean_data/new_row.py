import pandas as pd
import os

# --- Fichiers ---
OLD_FILE = "../data_tds_1.xlsx"  # ancien fichier
NEW_FILE = "../data_tds_2.xlsx"  # nouveau fichier
OUTPUT_FILE = "new_rows.csv"

def load_excel_with_header(file_path):
    """Détecte automatiquement la ligne d'entête et charge le fichier."""
    preview = pd.read_excel(file_path, header=None, nrows=30)
    header_row = None
    for i, row in preview.iterrows():
        if row.astype(str).str.contains("Nom", case=False, na=False).any():
            header_row = i
            break
    if header_row is None:
        raise ValueError(f"Impossible de trouver la ligne d'en-tête dans {file_path}")
    return pd.read_excel(file_path, header=header_row)

# Charger les deux fichiers
df_old = load_excel_with_header(OLD_FILE)
df_new = load_excel_with_header(NEW_FILE)

# Normalisation des colonnes (évite les erreurs de casse/espaces)
df_old.columns = df_old.columns.str.strip().str.lower()
df_new.columns = df_new.columns.str.strip().str.lower()

# Vérification des colonnes clés
if "e-mail" not in df_old.columns and "email" not in df_old.columns:
    raise ValueError("Colonne email manquante dans le fichier 1")
if "e-mail" not in df_new.columns and "email" not in df_new.columns:
    raise ValueError("Colonne email manquante dans le fichier 2")

# On choisit la bonne colonne email
email_col_old = "e-mail" if "e-mail" in df_old.columns else "email"
email_col_new = "e-mail" if "e-mail" in df_new.columns else "email"

# Normalisation des emails
df_old[email_col_old] = df_old[email_col_old].astype(str).str.strip().str.lower()
df_new[email_col_new] = df_new[email_col_new].astype(str).str.strip().str.lower()

# Détection des nouvelles lignes (emails qui n'étaient pas dans l'ancien fichier)
new_emails = set(df_new[email_col_new]) - set(df_old[email_col_old])

df_new_rows = df_new[df_new[email_col_new].isin(new_emails)]

# Sauvegarde dans un CSV avec les colonnes originales
df_new_rows.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

print(f"✅ {len(df_new_rows)} nouvelles lignes trouvées et sauvegardées dans {OUTPUT_FILE}")