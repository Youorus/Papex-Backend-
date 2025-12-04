import pdfkit
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone


def generate_receipt_pdf(receipt) -> bytes:
    """
    Génère le PDF d'un reçu de paiement
    avec total du service, payé aujourd'hui,
    payé cumulé et reste à payer.
    """

    # Toujours rafraîchir l'instance
    if receipt.pk:
        receipt.refresh_from_db()

    client = receipt.client
    lead = client.lead
    contract = receipt.contract

    # --- Calculs comptables ---
    if contract:
        # Montant total à payer (après remises)
        total_amount = getattr(contract, "real_amount_due", None)
        if total_amount is None:
            # fallback absolument sûr
            total_amount = getattr(contract, "amount_due", receipt.amount)

        # Total payé (tous les reçus)
        amount_paid_total = getattr(contract, "amount_paid", 0) or 0

        # Payé aujourd’hui (ce reçu)
        amount_today = receipt.amount

        # Total payé avant ce reçu
        amount_paid_before = amount_paid_total - amount_today
        if amount_paid_before < 0:
            amount_paid_before = 0  # protection

        # Reste dû
        remaining = total_amount - amount_paid_total
        if remaining < 0:
            remaining = 0  # protection
    else:
        # Pas de contrat → simple reçu libre
        total_amount = receipt.amount
        amount_today = receipt.amount
        amount_paid_total = receipt.amount
        amount_paid_before = 0
        remaining = 0

    # --- Dates ---
    payment_date_display = (
        receipt.payment_date.strftime("%d/%m/%Y")
        if receipt.payment_date else "—"
    )
    emission_date = timezone.now().strftime("%d/%m/%Y")

    # --- Contexte PDF ---
    context = {
        # --- Client ---
        "client_name": f"{lead.first_name} {lead.last_name}",
        "client_address": getattr(client, "adresse", "—"),
        "client_phone": lead.phone or "—",
        "client_email": lead.email or "—",

        # --- Service ---
        "service": contract.service.label if contract else "—",

        # --- Montants comptables formatés ---
        "total": f"{total_amount:.2f} €",
        "amount": f"{amount_today:.2f} €",
        "amount_before": f"{amount_paid_before:.2f} €",
        "amount_cumulative": f"{amount_paid_total:.2f} €",
        "remaining": f"{remaining:.2f} €",
        "mode": receipt.get_mode_display(),

        # --- Dates ---
        "date": emission_date,
        "payment_date": payment_date_display,

        # --- Entreprise ---
        "company": {
            "name": "SAS Papiers Express",
            "legal_form": "Société par Actions Simplifiée",
            "rcs": "R.C.S Paris 990 924 201",
            "address": "39 rue Navier, 75017 Paris",
            "contact_info": "contact@papiers-express.fr | www.papiers-express.fr",
            "logo_url": "https://papiers-express.fr/logo.png",
            "signature_url": "https://papiers-express.fr/signature.jpeg",
        },
    }

    # --- Rendu HTML ---
    html_string = render_to_string("recu/receipt_template.html", context)

    # --- Config PDF ---
    wkhtmltopdf_path = getattr(settings, "WKHTMLTOPDF_PATH", None)
    config = (
        pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
        if wkhtmltopdf_path else None
    )

    # --- Retour PDF ---
    try:
        return pdfkit.from_string(html_string, False, configuration=config)
    except Exception:
        # 🔥 Optionnel : raise explicit pour debug
        return pdfkit.from_string(html_string, False)
