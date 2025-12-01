from api.utils.email import send_html_email
from api.utils.email.config import TDS_FRANCE_ADDRESS, _build_context


def send_client_account_created_email(client):
    """
    Envoie un e-mail au client pour l’informer que son compte a été créé.
    """
    lead = client.lead  # On suppose que chaque client est lié à un lead
    context = _build_context(lead, None, TDS_FRANCE_ADDRESS)

    return send_html_email(
        to_email=lead.email,
        subject="Votre compte client TDS France a été créé",
        template_name="email/clients/client_account.html",
        context=context,
    )
