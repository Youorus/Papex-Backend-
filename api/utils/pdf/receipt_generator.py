# api/utils/pdf/receipt_generator.py

import pdfkit
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone


def generate_receipt_pdf(receipt) -> bytes:
    """
    Génère le PDF d'un reçu de paiement avec les données ACTUELLES.
    - receipt : instance PaymentReceipt (doit être rafraîchie si nécessaire)
    - Retour : bytes PDF prêt à stocker.
    """
    # ✅ S'assurer que l'instance est fraîche si elle vient d'être modifiée
    if receipt.pk:
        # Recharger depuis la base pour avoir les dernières données
        receipt.refresh_from_db()

    lead = receipt.client.lead
    contract = receipt.contract

    # ✅ Calculer les montants avec les données actuelles
    amount_paid = contract.amount_paid if contract else 0
    real_amount = contract.real_amount if contract else receipt.amount
    remaining_amount = real_amount - amount_paid

    # ✅ CORRECTION : Utiliser la date de paiement stockée en DB
    # Si payment_date existe, utiliser cette date, sinon utiliser maintenant
    payment_date_display = receipt.payment_date.strftime("%d/%m/%Y") if receipt.payment_date else "Date non définie"

    # Date d'émission du reçu (toujours maintenant)
    emission_date = timezone.now().strftime("%d/%m/%Y")

    context = {
        "receipt": receipt,
        "client_name": f"{lead.first_name} {lead.last_name}",
        "client_address": receipt.client.adresse or "Adresse non renseignée",
        "client_phone": lead.phone or "—",
        "client_email": lead.email or "—",
        "service": contract.service if contract else "Service non spécifié",
        "amount": f"{receipt.amount:.2f} €",
        "mode": receipt.get_mode_display(),
        "remaining": f"{remaining_amount:.2f} €",
        "date": emission_date,  # Date d'émission du reçu
        "payment_date": payment_date_display,  # ✅ Date réelle du paiement depuis la DB
        "company": {
            "name": "TDS France",
            "email": "contact@tds-france.fr",
            "website": "www.tds-france.fr",
            "siret": "928 184 043",
            "phones": ["01 85 09 01", "06 95 59 70 43"],
            "logo_url": "https://i.imgur.com/iSzPCvI.jpeg",
        },
    }

    html_string = render_to_string("recu/receipt_template.html", context)

    # ✅ Utilise wkhtmltopdf global si non précisé
    wkhtmltopdf_path = getattr(settings, "WKHTMLTOPDF_PATH", None)
    config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path) if wkhtmltopdf_path else None

    try:
        pdf_bytes = pdfkit.from_string(html_string, False, configuration=config)
        return pdf_bytes
    except Exception as e:
        # Logger l'erreur pour le débogage
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Erreur génération PDF reçu #{receipt.id}: {e}")
        raise