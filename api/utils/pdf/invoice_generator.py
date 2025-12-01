import pdfkit
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone

from api.contracts.models import Contract


def generate_invoice_pdf(contract: Contract) -> bytes:
    """
    Génère le PDF de la facture à partir du template HTML et retourne les bytes.
    - contract : instance de Contract à convertir en facture PDF.
    - Retour : bytes du PDF généré (prêt à uploader sur MinIO/S3).
    """
    client = contract.client
    lead = client.lead

    # ✅ Génération de la référence de facture (3 lettres maj + ID contrat)
    invoice_ref = f"TDS-{contract.id:06d}"

    # ✅ CORRECTION : Utiliser le MONTANT RÉEL (après remise) au lieu de amount_due
    montant_reel_ttc = contract.real_amount  # C'est le montant après remise

    from decimal import Decimal, ROUND_HALF_UP

    taux_tva = Decimal("0.20")  # 20%
    divisor = Decimal("1.20")   # 1 + 20%

    montant_ht = (montant_reel_ttc / divisor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    montant_tva = (montant_reel_ttc - montant_ht).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    context = {
        "invoice_ref": invoice_ref,
        "emission_date": timezone.now().strftime("%d/%m/%Y"),
        "due_date": timezone.now().strftime("%d/%m/%Y"),  # Même date pour émission et échéance
        "client_name": f"{lead.first_name} {lead.last_name}",
        "client_address": client.adresse or "Adresse non renseignée",
        "client_phone": lead.phone or "—",
        "client_email": lead.email or "—",
        "service": contract.service,
        "quantity": 1,  # Par défaut
        "unit_price_ht": f"{montant_ht:.2f} €",
        "tva_rate": "20%",
        "total_ht": f"{montant_ht:.2f} €",
        "total_ttc": f"{montant_reel_ttc:.2f} €",
        "montant_tva": f"{montant_tva:.2f} €",
        "base_ht": f"{montant_ht:.2f} €",
        "discount_percent": f"{contract.discount_percent:.2f}%",  # ✅ Ajout de la remise affichée
        "original_amount": f"{contract.amount_due:.2f} €",  # ✅ Montant avant remise
        "company": {
            "name": "TDS France",
            "email": "contact@tds-france.fr",
            "website": "www.tds-france.fr",
            "siret": "928 184 043",
            "tva_number": "FR10928B84043",
            "iban": "FR7630004005760001021633244",
            "bic": "BNPAFRPPXXX",
            "logo_url": "https://i.imgur.com/iSzPCvI.jpeg",
        },
    }

    html_string = render_to_string("factures/invoice_template.html", context)

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
        logger.error(f"Erreur génération PDF facture #{contract.id}: {e}")
        raise