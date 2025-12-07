import pdfkit
from decimal import Decimal, ROUND_HALF_UP
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone
from api.contracts.models import Contract


# =====================================================
# 🔹 CONSTANTES PAPIERS-EXPRESS (LOCALES AU MODULE)
# =====================================================

COMPANY_NAME = "SAS Papiers Express"
COMPANY_LEGAL_FORM = "Société par Actions Simplifiée"
COMPANY_RCS = "R.C.S Paris 990 924 201"
COMPANY_ADDRESS = "39 rue Navier, 75017 Paris"
COMPANY_CONTACT = "contact@papiers-express.fr | www.papiers-express.fr"

LOGO_URL = "https://papiers-express.fr/logo.png"
SIGNATURE_URL = "https://papiers-express.fr/signature.png"
STAMP_URL = "https://papiers-express.fr/cachet2.png"

DATE_FORMAT = "%d/%m/%Y"
CURRENCY_SUFFIX = " €"


# =====================================================
# 🔹 PDF FACTURE
# =====================================================

def generate_invoice_pdf(contract: Contract) -> bytes:
    """
    Génère le PDF de facture Papiers-Express.
    Retourne les bytes prêts à uploader.
    """

    # Rafraîchit l'instance en BDD
    contract.refresh_from_db()

    client = contract.client
    lead = client.lead

    # -----------------------------------------
    # Numéro de facture (format juridique propre)
    # -----------------------------------------
    invoice_ref = f"PAPEX-{contract.id:06d}"

    # -----------------------------------------
    # Calcul TVA / HT
    # -----------------------------------------
    montant_ttc = contract.real_amount  # Montant TTC après remise
    taux_tva = Decimal("0.20")
    divisor = Decimal("1.20")

    montant_ht = (
        montant_ttc / divisor
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    montant_tva = (
        montant_ttc - montant_ht
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # -----------------------------------------
    # Dates
    # -----------------------------------------
    emission_date = timezone.now().strftime(DATE_FORMAT)

    # -----------------------------------------
    # Contexte PDF
    # -----------------------------------------
    context = {
        "invoice_ref": invoice_ref,
        "emission_date": emission_date,
        "due_date": emission_date,

        # ------ Client ------
        "client_name": f"{lead.first_name} {lead.last_name}",
        "client_address": client.adresse or "—",
        "client_phone": lead.phone or "—",
        "client_email": lead.email or "—",

        # ------ Produit ------
        "service": contract.service.label if contract.service else "Prestation",
        "quantity": 1,
        "unit_price_ht": f"{montant_ht:.2f}{CURRENCY_SUFFIX}",
        "total_ht": f"{montant_ht:.2f}{CURRENCY_SUFFIX}",
        "total_ttc": f"{montant_ttc:.2f}{CURRENCY_SUFFIX}",
        "tva_rate": "20%",
        "montant_tva": f"{montant_tva:.2f}{CURRENCY_SUFFIX}",
        "base_ht": f"{montant_ht:.2f}{CURRENCY_SUFFIX}",

        # ------ Remise ------
        "discount_percent": f"{contract.discount_percent:.2f}%",
        "original_amount": f"{contract.amount_due:.2f}{CURRENCY_SUFFIX}",

        # ------ Société ------
        "company": {
            "name": COMPANY_NAME,
            "legal_form": COMPANY_LEGAL_FORM,
            "rcs": COMPANY_RCS,
            "address": COMPANY_ADDRESS,
            "contact": COMPANY_CONTACT,
            "logo_url": LOGO_URL,
            "signature_url": SIGNATURE_URL,
            "stamp_url": STAMP_URL,
        },
    }

    # -----------------------------------------
    # Génération HTML
    # -----------------------------------------
    html = render_to_string("factures/invoice_template.html", context)

    # -----------------------------------------
    # WKHTMLTOPDF
    # -----------------------------------------
    wkhtmltopdf_path = getattr(settings, "WKHTMLTOPDF_PATH", None)
    config = (
        pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
        if wkhtmltopdf_path else None
    )

    return (
        pdfkit.from_string(html, False, configuration=config)
        if config else pdfkit.from_string(html, False)
    )
