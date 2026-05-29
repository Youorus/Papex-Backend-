import logging
from datetime import timedelta
from django.utils import timezone
from django.db.models import Q
from django_q.tasks import async_task
from api.contracts.models import Contract
from api.utils.communication.dispatcher import CommunicationDispatcher

logger = logging.getLogger(__name__)

def run_payment_reminders():
    """
    Scanne les contrats non soldés et envoie des rappels pour les échéances J-7.
    """
    now = timezone.now().date()
    target_date = now + timedelta(days=7)
    
    # On cherche les contrats non soldés qui ont une échéance dans 7 jours EXACTEMENT
    # pour éviter les doublons quotidiens
    contracts = Contract.objects.filter(
        is_cancelled=False,
        receipts__next_due_date=target_date
    ).distinct()

    count = 0
    for contract in contracts:
        if not contract.is_fully_paid:
            send_payment_reminder_task(contract.id)
            count += 1
            
    logger.info(f"⏳ {count} rappels de paiement planifiés pour le {target_date}")
    return f"{count} reminders scheduled"

def _run_send_payment_reminder(contract_id: int):
    contract = Contract.objects.select_related("client__lead").get(id=contract_id)
    lead = contract.client.lead
    
    balance = contract.balance_due
    if balance <= 0:
        return

    subject = f"Rappel amical : votre échéance Papiers Express"
    
    # 🎨 TEMPLATE HTML CONTEXT
    context = {
        "contract": contract,
        "balance": f"{balance:.2f}",
        "due_date": (timezone.now().date() + timedelta(days=7)).strftime("%d/%m/%Y"),
        "client_name": f"{lead.first_name}"
    }
    
    # 📱 SMS BODY (Optimisé GSM)
    sms_body = (
        f"Bonjour {lead.first_name}, c'est Papiers Express. "
        f"Un petit rappel pour votre echeance de {balance:.2f} EUR prevue le "
        f"{(timezone.now().date() + timedelta(days=7)).strftime('%d/%m')}. "
        f"A bientot !"
    )

    # 🚀 DISPATCH (Force both Email and SMS for payments)
    CommunicationDispatcher.send_notification(
        lead=lead,
        subject=subject,
        template_prefix="payments/reminder",
        context=context,
        sms_body=sms_body,
        force_both=True
    )

from api.utils.pdf.financial_report_generator import generate_payment_status_report_pdf
from api.utils.email.config import send_html_email

def send_financial_status_report():
    """
    Génère le rapport PDF des encours et l'envoie à Marc et Themenain.
    """
    recipients = [
        "marc.takoumba@papiers-express.fr",
        "themenain.bamba@papiers-express.fr"
    ]
    
    try:
        pdf_bytes = generate_payment_status_report_pdf()
        today = timezone.now().strftime("%d/%m/%Y")
        
        subject = f"📊 Rapport Financier Quotidien - {today}"
        
        attachments = [{
            "filename": f"rapport_encours_{timezone.now().date()}.pdf",
            "content": pdf_bytes,
            "mimetype": "application/pdf"
        }]
        
        for email in recipients:
            send_html_email(
                to_email=email,
                subject=subject,
                template_name="email/internal/financial_report_notif.html",
                context={"date": today},
                attachments=attachments
            )
            
        logger.info(f"✅ Rapport financier envoyé à {len(recipients)} destinataires.")
        return True
    except Exception as e:
        logger.error(f"❌ Erreur génération/envoi rapport financier : {e}")
        return False

def send_payment_reminder_task(contract_id: int):
    async_task(
        "api.utils.communication.reminders._run_send_payment_reminder",
        contract_id,
        group="reminders"
    )
