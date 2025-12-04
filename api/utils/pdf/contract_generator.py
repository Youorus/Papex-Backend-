# api/utils/pdf/contract_generator.py

import pdfkit
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone

from api.contracts.models import Contract


# ============================================================================
# CONSTANTES POUR LA GÉNÉRATION DE CONTRAT
# ============================================================================

class ContractConstants:
    """Constantes centralisées pour la génération de contrats"""

    # Informations sur la société
    COMPANY_NAME = "SAS Papiers Express"
    COMPANY_LEGAL_FORM = "Société par Actions Simplifiée"
    COMPANY_RCS = "R.C.S Paris 990 924 201"
    COMPANY_ADDRESS = "39 rue Navier, 75017 Paris"
    COMPANY_CONTACT = "contact@papiers-express.fr | www.papiers-express.fr"

    # URLs des ressources
    LOGO_URL = "https://papiers-express.fr/logo.png"
    SIGNATURE_URL = "https://papiers-express.fr/signature.jpeg"

    # Préfixe de référence du contrat
    CONTRACT_REF_PREFIX = "PAPEX-C"

    # Liste factorisée des services
    SERVICES_LIST = [
        "Regroupement familial",
        "Obtention de titre de séjour",
        "Naturalisation",
        "Demande de visa",
        "Suivi de dossier en préfecture",
        "Duplicata de titre de séjour",
        "DCEM (Document de Circulation pour Enfant Mineur)",
        "Création d’entreprise",
        "Assistance juridique",
        "Contestation OQTF",
        "Inscription universitaire",
        "Effacement du casier judiciaire"
    ]

    # Formatage
    DATE_FORMAT = "%d/%m/%Y"
    CURRENCY_SUFFIX = " €"

    # Options PDF
    PDF_OPTIONS = {
        'page-size': 'A4',
        'margin-top': '15mm',
        'margin-right': '20mm',
        'margin-bottom': '15mm',
        'margin-left': '20mm',
        'encoding': "UTF-8",
        'no-outline': None,
        'enable-local-file-access': None,
    }

    # Chemin wkhtmltopdf
    @staticmethod
    def get_wkhtmltopdf_path():
        """Récupère le chemin de wkhtmltopdf depuis les settings"""
        return getattr(settings, "WKHTMLTOPDF_PATH", None)


# ============================================================================
# FONCTION PRINCIPALE DE GÉNÉRATION
# ============================================================================

def generate_contract_pdf(contract: Contract) -> bytes:
    """
    Génère le PDF du contrat à partir du template HTML et retourne les bytes.
    Version factorisée avec constantes centralisées.
    """

    client = contract.client
    lead = client.lead

    # Montant final après remise
    montant_reel = calculate_final_amount(contract)

    # Contexte transmis au template
    context = {
        # Informations de base
        "date": timezone.now().strftime(ContractConstants.DATE_FORMAT),
        "contract_id": contract.id,
        "contract_ref": f"{ContractConstants.CONTRACT_REF_PREFIX}-{contract.id}",

        # Client
        "first_name": lead.first_name,
        "last_name": lead.last_name,
        "phone": lead.phone,
        "email": lead.email,
        "service": contract.service.label,

        # Montant final formaté
        "montant": format_amount(montant_reel),

        # Liste factorisée
        "services_list": ContractConstants.SERVICES_LIST,

        # Société factorisée
        "company": {
            "name": ContractConstants.COMPANY_NAME,
            "legal_form": ContractConstants.COMPANY_LEGAL_FORM,
            "rcs": ContractConstants.COMPANY_RCS,
            "address": ContractConstants.COMPANY_ADDRESS,
            "contact_info": ContractConstants.COMPANY_CONTACT,
            "logo_url": ContractConstants.LOGO_URL,
            "signature_url": ContractConstants.SIGNATURE_URL,
        },

        # Informations de réduction éventuelles
        "discount_info": get_discount_info(contract) if contract.discount_percent else None,
    }

    # Génération du HTML
    html_string = render_to_string("contrats/contract_template.html", context)

    # Configuration de wkhtmltopdf
    wkhtmltopdf_path = ContractConstants.get_wkhtmltopdf_path()
    config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path) if wkhtmltopdf_path else None

    # Génération du PDF
    pdf_bytes = pdfkit.from_string(
        html_string,
        False,
        configuration=config,
        options=ContractConstants.PDF_OPTIONS
    )

    return pdf_bytes


# ============================================================================
# FONCTIONS HELPER
# ============================================================================

def calculate_final_amount(contract: Contract) -> float:
    """Calcule le montant final après réduction éventuelle"""

    if hasattr(contract, "real_amount_due") and contract.real_amount_due is not None:
        return float(contract.real_amount_due)

    amount = float(contract.amount_due)

    if contract.discount_percent:
        discount = amount * (float(contract.discount_percent) / 100)
        amount -= discount

    return amount


def format_amount(amount: float) -> str:
    """Formate un montant en euros"""
    return f"{amount:.2f}{ContractConstants.CURRENCY_SUFFIX}"


def get_discount_info(contract: Contract) -> dict:
    """Retourne les informations détaillées de la réduction"""
    return {
        "percent": f"{contract.discount_percent:.2f}%",
        "original_amount": format_amount(float(contract.amount_due)),
        "discount_amount": format_amount(
            float(contract.amount_due) * (float(contract.discount_percent) / 100)
        )
    }


# ============================================================================
# FONCTION POUR PRÉVISUALISATION (tests)
# ============================================================================

def get_contract_context(contract: Contract) -> dict:
    """Retourne le contexte sans générer le PDF"""

    client = contract.client
    lead = client.lead

    montant_reel = calculate_final_amount(contract)

    return {
        "date": timezone.now().strftime(ContractConstants.DATE_FORMAT),
        "contract_id": contract.id,
        "contract_ref": f"{ContractConstants.CONTRACT_REF_PREFIX}-{contract.id}",
        "first_name": lead.first_name,
        "last_name": lead.last_name,
        "phone": lead.phone,
        "email": lead.email,
        "service": contract.service.label,
        "montant": format_amount(montant_reel),
        "services_list": ContractConstants.SERVICES_LIST,
        "company": {
            "name": ContractConstants.COMPANY_NAME,
            "legal_form": ContractConstants.COMPANY_LEGAL_FORM,
            "rcs": ContractConstants.COMPANY_RCS,
            "address": ContractConstants.COMPANY_ADDRESS,
            "contact_info": ContractConstants.COMPANY_CONTACT,
            "logo_url": ContractConstants.LOGO_URL,
            "signature_url": ContractConstants.SIGNATURE_URL,
        },
    }
