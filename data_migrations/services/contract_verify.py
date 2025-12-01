#!/usr/bin/env python3
"""
Script de vérification des contrats mensuels
Compare les données du PDF avec la base de données Django
"""
import os
import sys
import django
from pathlib import Path
from decimal import Decimal
import re
from typing import Dict, List, Tuple
import tabula
import pandas as pd
from datetime import datetime

# Essayer de charger les variables d'environnement depuis .env
try:
    from load_env import load_dotenv

    load_dotenv()
except ImportError:
    pass

# Importer la configuration
try:
    from config import (
        DJANGO_SETTINGS_MODULE,
        AMOUNT_TOLERANCE,
        INCLUDE_CANCELLED_CONTRACTS,
        VERBOSE_PDF_EXTRACTION,
        REPORTS_DIRECTORY
    )
except ImportError:
    # ⚙️ CONFIGURATION DIRECTE - Modifiez ces valeurs selon vos besoins
    DJANGO_SETTINGS_MODULE = 'tds.settings.prod'  # 👈 Votre module Django settings
    AMOUNT_TOLERANCE = Decimal('0.01')  # 👈 Tolérance de comparaison en euros
    INCLUDE_CANCELLED_CONTRACTS = True  # 👈 True ou False
    VERBOSE_PDF_EXTRACTION = True  # 👈 True ou False
    REPORTS_DIRECTORY = './rapports'  # 👈 Répertoire des rapports

# ⚙️ CONFIGURATION DIRECTE DU PDF - Décommentez et modifiez pour exécution directe
PDF_PATH = "/Users/marc./Downloads/contracts_mai.pdf"  # 👈 Chemin de votre PDF
MONTH = 5  # 👈 Mois (1-12)
YEAR = 2025  # 👈 Année

# ⚙️ 1️⃣ Initialiser Django AVANT d'importer les modèles
if DJANGO_SETTINGS_MODULE:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", DJANGO_SETTINGS_MODULE)
django.setup()

# 2️⃣ Importer ensuite les modèles
from api.leads.models import Lead
from api.clients.models import Client
from api.contracts.models import Contract
from api.payments.models import PaymentReceipt


class ContractVerifier:
    """Classe pour vérifier la cohérence entre PDF et base de données"""

    def __init__(self, pdf_path: str, month: int, year: int):
        self.pdf_path = pdf_path
        self.month = month
        self.year = year
        self.discrepancies = []

    def normalize_phone(self, phone: str) -> str:
        """Normalise un numéro de téléphone pour la comparaison"""
        if not phone:
            return ""
        # Enlever tous les caractères non numériques
        phone = re.sub(r'\D', '', str(phone))
        # Si commence par 33, on garde tel quel
        if phone.startswith('33'):
            return phone
        # Si commence par 0, remplacer par 33
        if phone.startswith('0'):
            return '33' + phone[1:]
        # Sinon, ajouter 33
        return '33' + phone

    def extract_data_from_pdf(self) -> List[Dict]:
        """Extrait les données du PDF"""
        print(f"📄 Extraction des données du PDF: {self.pdf_path}")

        try:
            # Lire toutes les tables du PDF
            tables = tabula.read_pdf(
                self.pdf_path,
                pages='all',
                multiple_tables=True,
                pandas_options={'header': None}
            )

            contracts_data = []

            for table in tables:
                # Identifier les colonnes (basé sur votre PDF)
                # Colonnes: Nom, Prénom, Telephone, DATE, Statut CLIENT, Statut Paiement,
                #           Collaborateur, Prestation de service, TOTAL TTC, etc.

                for idx, row in table.iterrows():
                    # Ignorer les lignes d'en-tête et les lignes vides
                    if idx == 0 or pd.isna(row.iloc[0]):
                        continue

                    try:
                        # Extraire les données selon la structure du PDF
                        nom = str(row.iloc[0]).strip() if not pd.isna(row.iloc[0]) else ""
                        prenom = str(row.iloc[1]).strip() if not pd.isna(row.iloc[1]) else ""
                        telephone = str(row.iloc[2]).strip() if not pd.isna(row.iloc[2]) else ""
                        date_str = str(row.iloc[3]).strip() if not pd.isna(row.iloc[3]) else ""

                        # TOTAL TTC (colonne 8)
                        total_ttc_str = str(row.iloc[8]).strip() if len(row) > 8 and not pd.isna(row.iloc[8]) else ""

                        # Nettoyer le montant
                        total_ttc = self.parse_amount(total_ttc_str)

                        # Ignorer si pas de données valides
                        if not nom or not telephone or total_ttc == 0:
                            continue

                        contracts_data.append({
                            'nom': nom,
                            'prenom': prenom,
                            'telephone': self.normalize_phone(telephone),
                            'date': date_str,
                            'montant': total_ttc
                        })

                    except Exception as e:
                        print(f"⚠️ Erreur lors du traitement de la ligne {idx}: {e}")
                        continue

            print(f"✅ {len(contracts_data)} contrats extraits du PDF")
            return contracts_data

        except Exception as e:
            print(f"❌ Erreur lors de l'extraction du PDF: {e}")
            return []

    def parse_amount(self, amount_str: str) -> Decimal:
        """Parse un montant depuis une chaîne (ex: '1 590,00 €' -> 1590.00)"""
        if not amount_str:
            return Decimal('0.00')

        # Enlever les espaces et le symbole €
        amount_str = amount_str.replace('€', '').replace(' ', '').strip()

        # Remplacer la virgule par un point
        amount_str = amount_str.replace(',', '.')

        try:
            return Decimal(amount_str)
        except:
            return Decimal('0.00')

    def get_contracts_from_db(self) -> Dict[str, Contract]:
        """Récupère les contrats de la base de données pour le mois spécifié"""
        print(f"🗄️ Récupération des contrats de {self.month}/{self.year} depuis la DB")

        # Filtrer les contrats créés pendant le mois spécifié
        contracts_query = Contract.objects.filter(
            created_at__year=self.year,
            created_at__month=self.month
        )

        # Exclure les contrats annulés si configuré
        if not INCLUDE_CANCELLED_CONTRACTS:
            contracts_query = contracts_query.filter(is_cancelled=False)

        contracts = contracts_query.select_related('client', 'client__lead', 'service')

        # Créer un dictionnaire indexé par téléphone
        contracts_dict = {}

        for contract in contracts:
            lead = contract.client.lead
            phone = self.normalize_phone(lead.phone)

            # Utiliser le téléphone comme clé
            contracts_dict[phone] = contract

        print(f"✅ {len(contracts_dict)} contrats trouvés dans la DB")
        return contracts_dict

    def verify(self):
        """Effectue la vérification complète"""
        print(f"\n{'=' * 80}")
        print(f"🔍 VÉRIFICATION DES CONTRATS - {self.month:02d}/{self.year}")
        print(f"{'=' * 80}\n")

        # Extraire les données du PDF
        pdf_contracts = self.extract_data_from_pdf()

        # Récupérer les contrats de la DB
        db_contracts = self.get_contracts_from_db()

        # Vérifications
        self.check_missing_in_db(pdf_contracts, db_contracts)
        self.check_amount_discrepancies(pdf_contracts, db_contracts)
        self.check_missing_in_pdf(pdf_contracts, db_contracts)

        # Afficher le résumé
        self.print_summary()

    def check_missing_in_db(self, pdf_contracts: List[Dict], db_contracts: Dict):
        """Vérifie les contrats présents dans le PDF mais absents de la DB"""
        print("\n📋 Vérification des contrats manquants dans la DB...")

        missing_count = 0

        for pdf_contract in pdf_contracts:
            phone = pdf_contract['telephone']

            if phone not in db_contracts:
                missing_count += 1
                self.discrepancies.append({
                    'type': 'MANQUANT_DB',
                    'nom': pdf_contract['nom'],
                    'prenom': pdf_contract['prenom'],
                    'telephone': phone,
                    'montant_pdf': pdf_contract['montant'],
                    'date': pdf_contract['date']
                })
                print(f"  ❌ MANQUANT: {pdf_contract['prenom']} {pdf_contract['nom']} "
                      f"({phone}) - {pdf_contract['montant']}€")

        if missing_count == 0:
            print("  ✅ Tous les contrats du PDF sont dans la DB")

    def check_amount_discrepancies(self, pdf_contracts: List[Dict], db_contracts: Dict):
        """Vérifie les différences de montants"""
        print("\n💰 Vérification des montants...")

        discrepancy_count = 0
        tolerance = Decimal(str(AMOUNT_TOLERANCE))

        for pdf_contract in pdf_contracts:
            phone = pdf_contract['telephone']

            if phone in db_contracts:
                db_contract = db_contracts[phone]
                pdf_amount = pdf_contract['montant']
                db_amount = db_contract.amount_due

                # Comparer avec la tolérance configurée
                if abs(pdf_amount - db_amount) > tolerance:
                    discrepancy_count += 1
                    self.discrepancies.append({
                        'type': 'MONTANT_DIFFERENT',
                        'nom': pdf_contract['nom'],
                        'prenom': pdf_contract['prenom'],
                        'telephone': phone,
                        'montant_pdf': pdf_amount,
                        'montant_db': db_amount,
                        'difference': pdf_amount - db_amount
                    })
                    print(f"  ⚠️ DIFFÉRENCE: {pdf_contract['prenom']} {pdf_contract['nom']} "
                          f"({phone}) - PDF: {pdf_amount}€ / DB: {db_amount}€ "
                          f"(Diff: {pdf_amount - db_amount}€)")

        if discrepancy_count == 0:
            print("  ✅ Tous les montants correspondent")

    def check_missing_in_pdf(self, pdf_contracts: List[Dict], db_contracts: Dict):
        """Vérifie les contrats présents dans la DB mais absents du PDF"""
        print("\n📄 Vérification des contrats manquants dans le PDF...")

        # Créer un set des téléphones dans le PDF
        pdf_phones = {c['telephone'] for c in pdf_contracts}

        missing_count = 0

        for phone, db_contract in db_contracts.items():
            if phone not in pdf_phones:
                missing_count += 1
                lead = db_contract.client.lead
                self.discrepancies.append({
                    'type': 'MANQUANT_PDF',
                    'nom': lead.last_name,
                    'prenom': lead.first_name,
                    'telephone': phone,
                    'montant_db': db_contract.amount_due,
                    'contract_id': db_contract.id
                })
                print(f"  ⚠️ MANQUANT PDF: {lead.first_name} {lead.last_name} "
                      f"({phone}) - {db_contract.amount_due}€ - Contract ID: {db_contract.id}")

        if missing_count == 0:
            print("  ✅ Tous les contrats de la DB sont dans le PDF")

    def print_summary(self):
        """Affiche le résumé des vérifications"""
        print(f"\n{'=' * 80}")
        print("📊 RÉSUMÉ DES VÉRIFICATIONS")
        print(f"{'=' * 80}\n")

        if not self.discrepancies:
            print("✅ ✅ ✅ AUCUNE INCOHÉRENCE DÉTECTÉE! ✅ ✅ ✅")
            return

        # Compter par type
        missing_db = [d for d in self.discrepancies if d['type'] == 'MANQUANT_DB']
        missing_pdf = [d for d in self.discrepancies if d['type'] == 'MANQUANT_PDF']
        amount_diff = [d for d in self.discrepancies if d['type'] == 'MONTANT_DIFFERENT']

        print(f"⚠️ Total des incohérences: {len(self.discrepancies)}")
        print(f"  • Contrats manquants dans la DB: {len(missing_db)}")
        print(f"  • Contrats manquants dans le PDF: {len(missing_pdf)}")
        print(f"  • Différences de montants: {len(amount_diff)}")

        # Sauvegarder dans un fichier
        self.save_report()

    def save_report(self):
        """Sauvegarde le rapport dans un fichier"""
        # Créer le répertoire de rapports s'il n'existe pas
        os.makedirs(REPORTS_DIRECTORY, exist_ok=True)

        output_file = os.path.join(
            REPORTS_DIRECTORY,
            f"rapport_verification_{self.year}_{self.month:02d}.txt"
        )

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"RAPPORT DE VÉRIFICATION - {self.month:02d}/{self.year}\n")
            f.write(f"{'=' * 80}\n")
            f.write(f"Date de génération: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Module Django: {os.environ.get('DJANGO_SETTINGS_MODULE', 'Non défini')}\n")
            f.write(f"{'=' * 80}\n\n")

            if not self.discrepancies:
                f.write("✅ ✅ ✅ AUCUNE INCOHÉRENCE DÉTECTÉE! ✅ ✅ ✅\n")
            else:
                f.write(f"Total des incohérences: {len(self.discrepancies)}\n\n")

                for i, disc in enumerate(self.discrepancies, 1):
                    f.write(f"Incohérence #{i}\n")
                    f.write(f"Type: {disc['type']}\n")
                    f.write(f"Client: {disc['prenom']} {disc['nom']}\n")
                    f.write(f"Téléphone: {disc['telephone']}\n")

                    if 'montant_pdf' in disc:
                        f.write(f"Montant PDF: {disc['montant_pdf']}€\n")
                    if 'montant_db' in disc:
                        f.write(f"Montant DB: {disc['montant_db']}€\n")
                    if 'difference' in disc:
                        f.write(f"Différence: {disc['difference']}€\n")
                    if 'date' in disc:
                        f.write(f"Date (PDF): {disc['date']}\n")
                    if 'contract_id' in disc:
                        f.write(f"ID Contrat (DB): {disc['contract_id']}\n")

                    f.write("\n" + "-" * 80 + "\n\n")

        print(f"\n💾 Rapport sauvegardé dans: {output_file}")


def parse_arguments():
    """Parse les arguments de ligne de commande"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Vérification des contrats mensuels - Compare PDF et base de données Django',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples d'utilisation:
  python verify_contracts.py contracts_janvier.pdf 1 2025
  python verify_contracts.py --settings tds.settings.dev contracts_janvier.pdf 1 2025
  python verify_contracts.py -s myproject.settings.prod contracts_decembre.pdf 12 2024
        """
    )

    parser.add_argument(
        'pdf_path',
        help='Chemin vers le fichier PDF des contrats'
    )
    parser.add_argument(
        'month',
        type=int,
        choices=range(1, 13),
        help='Numéro du mois (1-12)'
    )
    parser.add_argument(
        'year',
        type=int,
        help='Année (ex: 2025)'
    )
    parser.add_argument(
        '--settings', '-s',
        dest='django_settings',
        help='Module Django settings à utiliser (ex: tds.settings.prod)'
    )

    return parser.parse_args()


def main():
    """Fonction principale"""
    # Utiliser les valeurs du code si définies, sinon parser les arguments
    try:
        # Vérifier si PDF_PATH est défini dans le code
        pdf_path = PDF_PATH
        month = MONTH
        year = YEAR
        print(f"📝 Utilisation de la configuration définie dans le code")
    except NameError:
        # Sinon, parser les arguments de ligne de commande
        args = parse_arguments()
        pdf_path = args.pdf_path
        month = args.month
        year = args.year

        # Si --settings est fourni, l'utiliser
        if args.django_settings:
            os.environ["DJANGO_SETTINGS_MODULE"] = args.django_settings
            print(f"📝 Utilisation du module Django: {args.django_settings}")

    # Vérifier que le fichier existe
    if not os.path.exists(pdf_path):
        print(f"❌ Fichier PDF introuvable: {pdf_path}")
        sys.exit(1)

    # Créer et lancer le vérificateur
    verifier = ContractVerifier(pdf_path, month, year)
    verifier.verify()


if __name__ == "__main__":
    main()