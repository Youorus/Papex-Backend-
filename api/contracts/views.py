"""
Vues REST API pour la gestion des contrats dans TDS France.

Cette vue inclut les fonctionnalités suivantes :
- Création et mise à jour des contrats
- Envoi de contrats signés
- Téléchargement et suppression des fichiers PDF
- Remboursement partiel ou total
- Recherche de reçus associés
- Envoi du contrat au client par e-mail via une tâche asynchrone
"""

from decimal import Decimal, InvalidOperation

from django.utils.text import slugify
from django.db import transaction
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import APIException

from api.contracts.models import Contract
from api.contracts.permissions import IsContractEditor
from api.contracts.serializer import ContractSerializer
from api.payments.models import PaymentReceipt
from api.payments.serializers import PaymentReceiptSerializer
from api.utils.email.contracts.tasks import send_contract_email_task


class ContractViewSet(viewsets.ModelViewSet):
    """
    ViewSet principal pour la gestion CRUD des contrats,
    avec endpoints pour uploads PDF, receipts et filtrage par client.
    """
    queryset = Contract.objects.select_related("client", "created_by").prefetch_related(
        "receipts"
    )
    serializer_class = ContractSerializer
    permission_classes = [IsContractEditor]

    @transaction.atomic
    def perform_create(self, serializer):

        contract = serializer.save(created_by=self.request.user)

        pdf_url = contract.generate_contract_pdf()
        if not pdf_url:
            raise APIException("Impossible de générer le PDF du contrat.")

        contract.contract_url = pdf_url
        contract.save(update_fields=["contract_url"])

        # --------------------------------------------------
        # Log LeadEvent CONTRACT_SIGNED → déclenche l'automation
        # Le lead est récupéré via client.lead
        # --------------------------------------------------
        try:
            from api.leads_events.models import LeadEvent

            lead = contract.client.lead
            LeadEvent.log(
                lead=lead,
                event_code="CONTRACT_SIGNED",
                actor=self.request.user,
                data={"contract_id": contract.id},
            )
        except Exception as e:
            # On ne bloque pas la création du contrat si le log échoue
            import logging
            logging.getLogger(__name__).error(
                "[ContractViewSet] Erreur log CONTRACT_SIGNED : %s", e
            )

    @action(detail=True, methods=["get"], url_path="receipts")
    def receipts(self, request, pk=None):
        """
        Retourne la liste des reçus de paiement associés au contrat.
        """
        contract = self.get_object()
        receipts = contract.receipts.all()
        serializer = PaymentReceiptSerializer(receipts, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="client/(?P<client_id>[^/.]+)")
    def list_by_client(self, request, client_id=None):
        """
        Liste les contrats filtrés par identifiant client.
        """
        contracts = self.queryset.filter(client_id=client_id)
        serializer = self.get_serializer(contracts, many=True)
        return Response(serializer.data)

    # ==========================================
    # Backend - views.py
    # ==========================================

    def partial_update(self, request, *args, **kwargs):
        """
        Met à jour partiellement un contrat.
        """
        instance = self.get_object()
        signed_contract = request.FILES.get("signed_contract")
        is_signed = request.data.get("is_signed", None)
        refund_amount = request.data.get("refund_amount", None)
        updated_fields = []

        if signed_contract:
            # Gérer l'upload du PDF signé
            if instance.contract_url:
                self._delete_file_from_url("contracts", instance.contract_url)
            instance.contract_url = self._save_signed_contract_pdf(instance, signed_contract)
            updated_fields.append("contract_url")

        if is_signed is not None:
            instance.is_signed = str(is_signed).lower() in ["true", "1"]
            updated_fields.append("is_signed")

        # ✅ Gérer le remboursement
        if refund_amount is not None:
            try:
                amount = Decimal(str(refund_amount))
                if amount < 0:
                    return Response(
                        {"detail": "Le montant remboursé ne peut pas être négatif."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                if amount > instance.amount_paid:
                    return Response(
                        {
                            "detail": f"Le remboursement ne peut pas dépasser le montant payé ({instance.amount_paid} €)."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                instance.refund_amount = amount
                instance.is_refunded = bool(amount > 0)
                updated_fields.extend(["refund_amount", "is_refunded"])
            except (InvalidOperation, TypeError):
                return Response(
                    {"detail": "Montant de remboursement invalide."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # MAJ des autres champs via serializer (service, amount_due, discount_percent)
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(self.get_serializer(instance).data)

    def destroy(self, request, *args, **kwargs):
        """
        Supprime un contrat ainsi que tous ses reçus,
        le PDF du contrat et le PDF de facture associé.
        """

        instance = self.get_object()

        # 1. Suppression des reçus PDF
        for receipt in instance.receipts.all():
            if receipt.receipt_url:
                try:
                    self._delete_file_from_url("receipts", receipt.receipt_url)
                except Exception as e:
                    print(f"Erreur suppression reçu PDF: {e}")

        # 2. Suppression du PDF contrat
        if instance.contract_url:
            try:
                self._delete_file_from_url("contracts", instance.contract_url)
            except Exception as e:
                print(f"Erreur suppression contrat PDF: {e}")

        # 3. ❗️ Suppression du PDF facture
        if instance.invoice_url:
            try:
                self._delete_file_from_url("invoices", instance.invoice_url)
            except Exception as e:
                print(f"Erreur suppression facture PDF: {e}")

        # 4. Suppression de l'objet (CASCADE receipts)
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="send-email")
    def send_email(self, request, pk=None):
        """
        Envoie le contrat par e-mail au client via une tâche Celery.

        Le contrat PDF est envoyé en pièce jointe si disponible.
        """
        contract = self.get_object()
        send_contract_email_task.delay(contract.id)
        return Response(
            {"detail": "📨 L'e-mail de contrat va être envoyé dans quelques instants."},
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=True, methods=["post"], url_path="cancel", permission_classes=[permissions.IsAdminUser])
    def cancel(self, request, pk=None):
        """
        ✅ Active/désactive le contrat (annule ou réactive).
        - Si le contrat est actif → on l'annule.
        - Si le contrat est annulé → on le réactive.
        """
        contract = self.get_object()

        if contract.is_cancelled:
            # Réactivation
            contract.is_cancelled = False
        else:
            # Annulation
            contract.is_cancelled = True

        contract.save(update_fields=["is_cancelled"])

        return Response({ "is_cancelled": contract.is_cancelled})

    @action(detail=True, methods=["post"], url_path="refund")
    def refund(self, request, pk=None):
        """
        Applique un remboursement partiel ou total sur un contrat existant.
        """
        contract = self.get_object()
        raw_amount = request.data.get("refund_amount")
        refund_note = request.data.get("refund_note")

        try:
            amount = Decimal(str(raw_amount))
        except (InvalidOperation, TypeError):
            return Response(
                {"detail": "Montant invalide."}, status=status.HTTP_400_BAD_REQUEST
            )

        valid, message = self._is_valid_refund_amount(contract, amount)
        if not valid:
            return Response({"detail": message}, status=status.HTTP_400_BAD_REQUEST)

        # Appliquer le remboursement (on cumule)
        already_refunded = contract.refund_amount or Decimal("0.00")
        contract.refund_amount = already_refunded + amount
        contract.is_refunded = bool(
            contract.refund_amount and contract.refund_amount > 0
        )

        partial_data = {
            "refund_amount": str(contract.refund_amount),
            "is_refunded": contract.is_refunded,
        }
        if refund_note is not None:
            partial_data["refund_note"] = refund_note

        serializer = self.get_serializer(contract, data=partial_data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        return Response(serializer.data, status=status.HTTP_200_OK)

    def _delete_file_from_url(self, bucket_key: str, file_url: str):
        """
        Supprime un fichier du storage MinIO à partir de son URL.
        """
        try:
            from django.conf import settings
            from api.utils.cloud.scw.bucket_utils import delete_object

            bucket = settings.SCW_BUCKETS[bucket_key]
            split_token = f"/{bucket}/"
            path = file_url.split(split_token, 1)[-1]
            delete_object(bucket_key, path)
        except Exception as e:
            print(f"Erreur suppression fichier S3: {e}")

    def _save_signed_contract_pdf(self, instance, file):
        """
        Sauvegarde un contrat signé dans le storage.
        """
        from django.conf import settings
        from api.utils.cloud.scw.bucket_utils import put_object

        client = instance.client
        lead = client.lead
        client_slug = slugify(f"{lead.last_name}_{lead.first_name}_{client.id}")
        date_str = instance.created_at.strftime("%Y%m%d")
        filename = f"{client_slug}/contrat_{instance.id}_{date_str}.pdf"
        put_object(
            "contracts", filename, content=file.read(), content_type=file.content_type
        )
        return f"{settings.AWS_S3_ENDPOINT_URL.rstrip('/')}/{settings.SCW_BUCKETS['contracts']}/{filename}"

    def _is_valid_refund_amount(self, contract, amount: Decimal) -> tuple[bool, str]:
        """
        Vérifie si un montant de remboursement est valide par rapport au montant payé.
        """
        already_paid = contract.amount_paid
        already_refunded = contract.refund_amount or Decimal("0.00")
        max_refundable = already_paid - already_refunded

        if amount <= 0:
            return False, "Le montant doit être supérieur à 0."
        if amount > max_refundable:
            return (
                False,
                f"Le montant dépasse le maximum remboursable ({max_refundable} €).",
            )
        return True, ""

    @action(detail=True, methods=["post"], url_path="generate-invoice")
    def generate_invoice(self, request, pk=None):
        """
        Génère manuellement une facture pour ce contrat.
        """
        contract = self.get_object()

        try:
            if contract.invoice_url:
                return Response({
                    "detail": "Une facture existe déjà pour ce contrat.",
                    "invoice_url": contract.invoice_url,
                    "existing": True
                }, status=200)

            invoice_url = contract.generate_invoice_pdf()

            if invoice_url:
                return Response({
                    "detail": "Facture générée avec succès.",
                    "invoice_url": invoice_url,
                    "contract_id": contract.id,
                    "is_fully_paid": contract.is_fully_paid,
                    "balance_due": str(contract.balance_due),
                    "real_amount": str(contract.real_amount)
                }, status=200)
            else:
                return Response({
                    "detail": "Erreur lors de la génération de la facture."
                }, status=500)

        except Exception as e:
            return Response({
                "detail": f"Erreur technique: {str(e)}"
            }, status=500)
