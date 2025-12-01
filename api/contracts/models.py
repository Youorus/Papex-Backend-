from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Contract(models.Model):
    """
    Modèle représentant un contrat client, lié à un service, un utilisateur créateur et un client.
    - Gère le montant, remise, PDF, paiements et signature.
    """

    client = models.ForeignKey(
        "clients.Client", on_delete=models.CASCADE, related_name="contracts"
    )
    created_by = models.ForeignKey(
        "users.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    service = models.ForeignKey(
        "services.Service", on_delete=models.PROTECT, related_name="contracts"
    )
    amount_due = models.DecimalField(
        _("Montant dû (€)"), max_digits=10, decimal_places=2
    )
    discount_percent = models.DecimalField(
        _("Remise (%)"), max_digits=5, decimal_places=2, default=Decimal("0.00")
    )
    contract_url = models.URLField(_("Contrat PDF"), max_length=1024, blank=True, null=True)
    invoice_url = models.URLField(_("Facture PDF"), max_length=1024, blank=True, null=True)
    created_at = models.DateTimeField(_("Créé le"), default=timezone.now)
    is_signed = models.BooleanField(_("Signé ?"), default=False)
    is_refunded = models.BooleanField(default=False)
    is_cancelled = models.BooleanField(default=False)
    refund_amount = models.DecimalField(
        _("Montant remboursé (€)"),
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("contrat")
        verbose_name_plural = _("contrats")

    @property
    def real_amount(self):
        """Montant réel dû après remise."""
        ratio = Decimal("1.00") - (self.discount_percent / Decimal("100.00"))
        return (self.amount_due * ratio).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    @property
    def amount_paid(self):
        """Somme totale déjà payée via les reçus liés.
        Retourne 0.00 si l'objet n'a pas encore de PK (non sauvegardé)."""
        if not self.pk:
            return Decimal("0.00")
        return sum(receipt.amount for receipt in self.receipts.all())

    @property
    def net_paid(self):
        """Total payé après déduction des remboursements."""
        refund = self.refund_amount or Decimal("0.00")
        total = Decimal(self.amount_paid) - refund
        return total if total > 0 else Decimal("0.00")

    @property
    def balance_due(self):
        """Solde restant dû (montant réel - payé net)."""
        remaining = self.real_amount - self.net_paid
        return (
            remaining.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if remaining > 0
            else Decimal("0.00")
        )

    @property
    def is_fully_paid(self):
        """Contrat soldé si le solde restant dû est nul."""
        return self.balance_due == Decimal("0.00")

    def __str__(self):
        return (
            f"Contrat {self.id} - {getattr(self.client, 'full_name', self.client.pk)}"
        )

    def clean(self):
        super().clean()
        # Normaliser le refund_amount à 0 si None
        if self.refund_amount is None:
            self.refund_amount = Decimal("0.00")
        # Interdire les montants négatifs
        if self.refund_amount < 0:
            raise ValidationError(
                {"refund_amount": _("Le montant remboursé ne peut pas être négatif.")}
            )
        # Un remboursement ne peut pas dépasser le total payé (avant remboursement)
        # Vérification uniquement si l'objet est sauvegardé (possède une PK)
        if self.pk and self.refund_amount > Decimal(self.amount_paid):
            raise ValidationError(
                {
                    "refund_amount": _(
                        "Le remboursement ne peut pas dépasser le total payé."
                    )
                }
            )

    def save(self, *args, **kwargs):
        # Cohérence booléen/valeur
        if self.refund_amount is None:
            self.refund_amount = Decimal("0.00")
        self.is_refunded = bool(self.refund_amount and self.refund_amount > 0)
        self.full_clean()
        return super().save(*args, **kwargs)

    def apply_refund(self, amount: Decimal):
        """Applique un remboursement additionnel et persiste la cohérence."""
        if amount is None:
            amount = Decimal("0.00")
        if amount <= 0:
            raise ValidationError(
                {"refund_amount": _("Le montant de remboursement doit être positif.")}
            )
        self.refund_amount = (self.refund_amount or Decimal("0.00")) + Decimal(amount)
        self.save(update_fields=["refund_amount", "is_refunded"])

    def generate_contract_pdf(self):
        """
        Génère un PDF pour le contrat (stockage cloud).
        Renvoie l'URL du contrat PDF si la génération réussit.
        """
        if self.contract_url:
            print("ℹ️ PDF déjà généré, URL :", self.contract_url)
            return self.contract_url

        from api.utils.cloud.storage import store_contract_pdf
        from api.utils.pdf.contract_generator import generate_contract_pdf

        print(f"📄 Génération PDF pour contrat #{self.pk}...")
        try:
            pdf_bytes = generate_contract_pdf(self)
            contract_url = store_contract_pdf(self, pdf_bytes)
            if contract_url:
                self.contract_url = contract_url
                # ✅ MAJ persistée côté base
                Contract.objects.filter(pk=self.pk).update(contract_url=contract_url)
                print("✅ Contrat PDF généré :", contract_url)
            else:
                print("⚠️ Aucune URL retournée par store_contract_pdf")
            return contract_url
        except Exception as e:
            print(f"❌ Erreur lors de la génération du contrat PDF : {e}")
            return None

    def generate_invoice_pdf(self):
        """
        Génère un PDF de facture pour le contrat (stockage cloud).
        Renvoie l'URL de la facture PDF si la génération réussit.
        """
        if self.invoice_url:
            print("ℹ️ Facture PDF déjà générée, URL :", self.invoice_url)
            return self.invoice_url

        from api.utils.cloud.storage import store_invoice_pdf
        from api.utils.pdf.invoice_generator import generate_invoice_pdf

        print(f"🧾 Génération facture PDF pour contrat #{self.pk}...")
        try:
            pdf_bytes = generate_invoice_pdf(self)
            invoice_ref = f"TDS-{self.id:06d}"  # Même référence que dans le template
            invoice_url = store_invoice_pdf(self, pdf_bytes, invoice_ref)
            if invoice_url:
                self.invoice_url = invoice_url
                # ✅ MAJ persistée côté base
                Contract.objects.filter(pk=self.pk).update(invoice_url=invoice_url)
                print("✅ Facture PDF générée :", invoice_url)
            else:
                print("⚠️ Aucune URL retournée par store_invoice_pdf")
            return invoice_url
        except Exception as e:
            print(f"❌ Erreur lors de la génération de la facture PDF : {e}")
            return None