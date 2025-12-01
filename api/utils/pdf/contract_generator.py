# api/utils/pdf/contract_generator.py

import pdfkit
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone

from api.contracts.models import Contract


def generate_contract_pdf(contract: Contract) -> bytes:
    """
    Génère le PDF du contrat à partir du template HTML et retourne les bytes.
    """
    client = contract.client
    lead = client.lead

    # 🧮 Calcul du montant réel après remise
    if hasattr(contract, "real_amount_due") and contract.real_amount_due is not None:
        montant_reel = contract.real_amount_due
    else:
        montant_reel = contract.amount_due
        if contract.discount_percent:
            montant_reel -= contract.amount_due * (contract.discount_percent / 100)

    context = {
        "date": timezone.now().strftime("%d/%m/%Y"),
        "first_name": lead.first_name,
        "last_name": lead.last_name,
        "phone": lead.phone,
        "email": lead.email,
        "service": contract.service.label,

        # 🧾 Montant avec remise appliquée
        "montant": f"{montant_reel:.2f} €",

        # Pour affichage informatif
        "discount": f"{contract.discount_percent:.2f} %",
        "company": {
            "name": "TDS France",
            "email": "contact@tds-france.fr",
            "website": "www.tds-france.fr",
            "siret": "928 184 043",
            "logo_url": "https://i.imgur.com/iSzPCvI.jpeg",
        },
    }

    html_string = render_to_string("contrats/contract_template.html", context)

    wkhtmltopdf_path = getattr(settings, "WKHTMLTOPDF_PATH", None)
    config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path) if wkhtmltopdf_path else None

    pdf_bytes = pdfkit.from_string(html_string, False, configuration=config)

    return pdf_bytes