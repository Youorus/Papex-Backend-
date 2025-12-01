import re
import pdfplumber
import pandas as pd

pdf_file = "/Users/marc./Downloads/contracts_decembre.pdf"
output_file = "contracts_cleaned.csv"
month_to_extract = 1      # Mois sous forme d'entier
year_to_extract = 2025     # Année sous forme d'entier

def extract_contracts(pdf_path, month, year):
    contracts = []
    phone_pattern = re.compile(r"\b\d{9,11}\b")        # Numéro de téléphone
    # ✅ Regex accepte "2/12" ou "2/12/2024"
    date_pattern = re.compile(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b")
    price_pattern = re.compile(r"\d{1,3}(?:\s?\d{3})*,\d{2}")  # ex: 1 190,00 ou 890,00

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text()
            if not text:
                continue

            for line in text.split("\n"):
                phone_match = phone_pattern.search(line)
                date_match = date_pattern.search(line)
                if phone_match and date_match:
                    raw_date = date_match.group(0)
                    try:
                        # --- Normalisation de la date ---
                        parts = raw_date.split("/")
                        day = int(parts[0])
                        month_found = int(parts[1])
                        year_found = int(parts[2]) if len(parts) > 2 else year
                    except ValueError:
                        continue  # si la date est mal formée

                    # --- Vérifie si le mois correspond ---
                    if month_found == month and year_found == year:
                        name_part = line.split(phone_match.group(0))[0].strip()
                        phone = phone_match.group(0)
                        date = f"{day:02d}/{month_found:02d}/{year_found}"
                        price_match = price_pattern.search(line)
                        total = price_match.group(0) if price_match else ""

                        contracts.append({
                            "Nom complet": name_part,
                            "Téléphone": phone,
                            "Date du contrat": date,
                            "Montant TTC": total
                        })
    return contracts


# --- Extraction ---
contracts = extract_contracts(pdf_file, month_to_extract, year_to_extract)

# --- Export propre ---
df = pd.DataFrame(contracts)
df.to_csv(output_file, index=False, encoding="utf-8-sig")

print(f"✅ Extraction propre terminée pour {month_to_extract:02d}/{year_to_extract}")
print(f"{len(df)} contrats trouvés")
print(f"Résultats enregistrés dans : {output_file}")
