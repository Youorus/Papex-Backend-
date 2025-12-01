from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from api.payments.enums import PaymentMode
from api.utils.cloud.storage import store_receipt_pdf
from api.utils.pdf.receipt_generator import generate_receipt_pdf


class PaymentReceipt(models.Model):
    """
    Modèle de reçu de paiement lié à un client et éventuellement un contrat.
    """

    client = models.ForeignKey(
        "clients.Client", on_delete=models.CASCADE, related_name="receipts"
    )
    contract = models.ForeignKey(
        "contracts.Contract",
        on_delete=models.CASCADE,
        related_name="receipts",
        null=True,
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    mode = models.CharField(max_length=20, choices=PaymentMode.choices)
    payment_date = models.DateTimeField(default=timezone.now)
    next_due_date = models.DateField(
        null=True,
        blank=True,
        help_text=_(
            "Date de la prochaine échéance prévue si le contrat n'est pas encore soldé."
        ),
    )
    receipt_url = models.URLField(blank=True, null=True)
    created_by = models.ForeignKey(
        "users.User", on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        ordering = ["-payment_date"]

    def __str__(self):
        return f"Reçu {self.amount:.2f} € - {self.client} - {self.payment_date.date()}"

    def generate_pdf(self):
        """
        Génère un reçu PDF et met à jour son URL.
        """
        pdf_bytes = generate_receipt_pdf(self)
        url = store_receipt_pdf(self, pdf_bytes)
        if url:
            # ✅ CORRECTION : Mettre à jour l'instance en mémoire ET en base
            self.receipt_url = url
            # Sauvegarder uniquement le champ receipt_url
            self.save(update_fields=["receipt_url"])
            return url
        return None