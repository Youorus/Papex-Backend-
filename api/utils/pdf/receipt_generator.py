import pdfkit
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone

# ============================================================================
# CONSTANTES GÉNÉRIQUES POUR LES REÇUS
# ============================================================================

class ReceiptConstants:
    """Constantes centralisées pour la génération des reçus PDF."""

    # ----------------------------------
    # Informations société
    # ----------------------------------
    COMPANY_NAME = "SAS Papiers Express"
    COMPANY_LEGAL_FORM = "Société par Actions Simplifiée"
    COMPANY_RCS = "R.C.S Paris 990 924 201"
    COMPANY_ADDRESS = "39 rue Navier, 75017 Paris"
    COMPANY_CONTACT = "contact@papiers-express.fr | www.papiers-express.fr"

    # ----------------------------------
    # URLs ressources
    # ----------------------------------
    LOGO_URL = "https://papiers-express.fr/logo.png"
    SIGNATURE_URL = "https://papiers-express.fr/signature.png"
    STAMP_URL = "https://papiers-express.fr/cachet2.png"

    # ----------------------------------
    # Formatage
    # ----------------------------------
    DATE_FORMAT = "%d/%m/%Y"
    CURRENCY_SUFFIX = " €"

    # ----------------------------------
    # WKHTMLTOPDF CONFIG
    # ----------------------------------
    PDF_OPTIONS = {
        "page-size": "A4",
        "margin-top": "15mm",
        "margin-right": "18mm",
        "margin-bottom": "15mm",
        "margin-left": "18mm",
        "encoding": "UTF-8",
        "no-outline": None,
        "enable-local-file-access": None,
    }

    @staticmethod
    def wkhtmltopdf_path():
        return getattr(settings, "WKHTMLTOPDF_PATH", None)


# ============================================================================
# HELPERS PDF
# ============================================================================

def format_amount(value: float) -> str:
    """formatte un montant en euros, toujours 2 décimales."""
    try:
        return f"{float(value):.2f}{ReceiptConstants.CURRENCY_SUFFIX}"
    except Exception:
        return f"{value}{ReceiptConstants.CURRENCY_SUFFIX}"


def format_date(dt) -> str:
    """Sécurise l'affichage date."""
    if not dt:
        return "—"
    try:
        return dt.strftime(ReceiptConstants.DATE_FORMAT)
    except Exception:
        return str(dt)


# ============================================================================
# FONCTION PRINCIPALE
# ============================================================================

def generate_receipt_pdf(receipt) -> bytes:
    """
    Génère le PDF d'un reçu de paiement,
    avec les montants cumulés liés au contrat.
    """

    if receipt.pk:
        receipt.refresh_from_db()

    client = receipt.client
    lead = client.lead
    contract = receipt.contract

    # =======================================================================
    # LOGIQUE COMPTABLE FACTORISÉE
    # =======================================================================
    if contract:
        # Montant total dû
        total = getattr(contract, "real_amount_due", None)
        if total is None:
            total = getattr(contract, "amount_due", receipt.amount)

        # Total payé cumulé
        amount_paid_total = getattr(contract, "amount_paid", 0) or 0

        # Montant payé aujourd’hui
        amount_today = receipt.amount

        # Payé avant ce reçu
        amount_before = amount_paid_total - amount_today
        if amount_before < 0:
            amount_before = 0

        # Reste dû
        remaining = total - amount_paid_total
        if remaining < 0:
            remaining = 0

        service_label = contract.service.label
    else:
        # reçu simple sans contrat
        service_label = "—"
        total = receipt.amount
        amount_today = receipt.amount
        amount_paid_total = receipt.amount
        amount_before = 0
        remaining = 0

    # =======================================================================
    # DATES
    # =======================================================================
    payment_date_display = format_date(receipt.payment_date)
    emission_date = format_date(timezone.now())

    # =======================================================================
    # CONTEXTE
    # =======================================================================
    context = {
        # --- CLIENT ---
        "client_name": f"{lead.first_name} {lead.last_name}",
        "client_address": getattr(client, "adresse", "—"),
        "client_phone": lead.phone or "—",
        "client_email": lead.email or "—",

        # --- SERVICE ---
        "service": service_label,

        # --- MONTANTS ---
        "total": format_amount(total),
        "amount": format_amount(amount_today),
        "amount_before": format_amount(amount_before),
        "amount_cumulative": format_amount(amount_paid_total),
        "remaining": format_amount(remaining),
        "mode": receipt.get_mode_display(),

        # --- DATES ---
        "date": emission_date,
        "payment_date": payment_date_display,

        # --- SOCIÉTÉ ---
        "company": {
            "name": ReceiptConstants.COMPANY_NAME,
            "legal_form": ReceiptConstants.COMPANY_LEGAL_FORM,
            "rcs": ReceiptConstants.COMPANY_RCS,
            "address": ReceiptConstants.COMPANY_ADDRESS,
            "contact_info": ReceiptConstants.COMPANY_CONTACT,
            "logo_url": ReceiptConstants.LOGO_URL,
            "signature_url": ReceiptConstants.SIGNATURE_URL,
            "stamp_url": ReceiptConstants.STAMP_URL,
        },
    }

    # =======================================================================
    # RENDU HTML
    # =======================================================================
    html_string = render_to_string(
        "recu/receipt_template.html",
        context
    )

    # =======================================================================
    # CONFIG PDF
    # =======================================================================
    cfg = None
    path = ReceiptConstants.wkhtmltopdf_path()
    if path:
        cfg = pdfkit.configuration(wkhtmltopdf=path)

    # =======================================================================
    # GÉNÉRATION PDF
    # =======================================================================
    return pdfkit.from_string(
        html_string,
        False,
        configuration=cfg,
        options=ReceiptConstants.PDF_OPTIONS
    )
