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

    COMPANY_NAME = "SAS Papiers Express"
    COMPANY_LEGAL_FORM = "Société par Actions Simplifiée"
    COMPANY_RCS = "R.C.S Paris 990 924 201"
    COMPANY_ADDRESS = "39 rue Navier, 75017 Paris"
    COMPANY_CONTACT = "contact@papiers-express.fr | www.papiers-express.fr"
    STAMP_URL = "https://papiers-express.fr/cachet2.png"
    LOGO_URL = "https://papiers-express.fr/logo.png"
    SIGNATURE_URL = "https://papiers-express.fr/signature.png"

    CONTRACT_REF_PREFIX = "PAPEX"

    SERVICES_LIST = [
        "Regroupement familial",
        "Obtention de titre de séjour",
        "Naturalisation",
        "Demande de visa",
        "Suivi de dossier en préfecture",
        "Duplicata de titre de séjour",
        "DCEM (Document de Circulation pour Enfant Mineur)",
        "Création d'entreprise",
        "Assistance juridique",
        "Contestation OQTF",
        "Inscription universitaire",
        "Effacement du casier judiciaire"
    ]

    DATE_FORMAT = "%d/%m/%Y"
    CURRENCY_SUFFIX = " €"

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

    @staticmethod
    def get_wkhtmltopdf_path():
        return getattr(settings, "WKHTMLTOPDF_PATH", None)


# ============================================================================
# HELPERS
# ============================================================================

def format_amount(amount: float) -> str:
    """Formate un montant en euros."""
    try:
        return f"{float(amount):.2f}{ContractConstants.CURRENCY_SUFFIX}"
    except Exception:
        return f"{amount}{ContractConstants.CURRENCY_SUFFIX}"


def format_date(dt) -> str:
    """Sécurise l'affichage date en convertissant en heure locale (Europe/Paris)."""
    if not dt:
        return "—"
    try:
        # Si c'est un datetime aware (avec timezone), convertir en heure locale
        if hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
            dt = timezone.localtime(dt)
        return dt.strftime(ContractConstants.DATE_FORMAT)
    except Exception:
        return str(dt)


def calculate_final_amount(contract: Contract) -> float:
    """Calcule le montant final après réduction éventuelle."""
    if hasattr(contract, "real_amount_due") and contract.real_amount_due is not None:
        return float(contract.real_amount_due)

    amount = float(contract.amount_due)
    if contract.discount_percent:
        discount = amount * (float(contract.discount_percent) / 100)
        amount -= discount

    return amount


def get_discount_info(contract: Contract) -> dict:
    """Retourne les informations détaillées de la réduction."""
    return {
        "percent": f"{contract.discount_percent:.2f}%",
        "original_amount": format_amount(float(contract.amount_due)),
        "discount_amount": format_amount(
            float(contract.amount_due) * (float(contract.discount_percent) / 100)
        ),
    }


# ============================================================================
# FONCTION PRINCIPALE DE GÉNÉRATION
# ============================================================================

def generate_contract_pdf(contract: Contract) -> bytes:
    """
    Génère le PDF du contrat à partir du template HTML et retourne les bytes.
    """
    client = contract.client
    lead = client.lead

    montant_reel = calculate_final_amount(contract)

    context = {
        # Informations de base
        "date": format_date(timezone.now()),
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

        # Société
        "company": {
            "name": ContractConstants.COMPANY_NAME,
            "legal_form": ContractConstants.COMPANY_LEGAL_FORM,
            "rcs": ContractConstants.COMPANY_RCS,
            "address": ContractConstants.COMPANY_ADDRESS,
            "contact_info": ContractConstants.COMPANY_CONTACT,
            "logo_url": ContractConstants.LOGO_URL,
            "signature_url": ContractConstants.SIGNATURE_URL,
            "stamp_url": ContractConstants.STAMP_URL,
        },

        # Réduction éventuelle
        "discount_info": get_discount_info(contract) if contract.discount_percent else None,
    }

    html_string = render_to_string("contrats/contract_template.html", context)

    wkhtmltopdf_path = ContractConstants.get_wkhtmltopdf_path()
    config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path) if wkhtmltopdf_path else None

    return pdfkit.from_string(
        html_string,
        False,
        configuration=config,
        options=ContractConstants.PDF_OPTIONS,
    )


# ============================================================================
# FONCTION POUR PRÉVISUALISATION (tests)
# ============================================================================

def get_contract_context(contract: Contract) -> dict:
    """Retourne le contexte sans générer le PDF."""
    client = contract.client
    lead = client.lead
    montant_reel = calculate_final_amount(contract)

    return {
        "date": format_date(timezone.now()),
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