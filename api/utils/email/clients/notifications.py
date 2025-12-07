from api.utils.email import send_html_email
from api.utils.email.config import _build_context


def send_client_account_created_email(client):
    """
    Envoie un e-mail au client pour l’informer que son espace client a été créé.
    """
    lead = getattr(client, "lead", None)
    if not lead or not lead.email:
        return

    context = _build_context(
        lead,
        extra={
            "client": client,
        },
    )

    return send_html_email(
        to_email=lead.email,
        subject="Votre espace client est maintenant disponible – Papiers Express",
        template_name="email/clients/client_account.html",
        context=context,
    )
