# api/payments/views.py
# ✅ Migré Celery (.delay()) → Django-Q2 (appels directs dispatchers)

import logging
from decimal import Decimal
from collections import defaultdict
import threading

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from datetime import date, datetime

from api.leads.models import Lead
from api.payments.models import PaymentReceipt
from api.payments.permissions import IsPaymentEditor
from api.payments.serializers import PaymentReceiptSerializer

# ✅ Import des dispatchers Django-Q2 (plus de .delay())
from api.utils.email.recus.tasks import (
    send_receipts_email_task,
    send_due_date_updated_email_task,
)

logger = logging.getLogger(__name__)

FIELDS_THAT_REQUIRE_RECEIPT_PDF_REGEN = {"amount", "mode", "mode_detail", "payment_date"}


class PaymentReceiptViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentReceiptSerializer
    permission_classes = [IsPaymentEditor]

    def get_queryset(self):
        queryset = PaymentReceipt.objects.select_related("client", "contract", "created_by")
        contract_id = self.request.query_params.get("contract_id")
        if contract_id:
            queryset = queryset.filter(contract_id=contract_id)
        return queryset.order_by("-payment_date")

    def _check_and_generate_invoice(self, contract):
        try:
            contract.refresh_from_db()
            if contract.is_fully_paid and not contract.invoice_url:
                logger.info("🎉 Contrat #%s entièrement payé — génération facture...", contract.id)
                invoice_url = contract.generate_invoice_pdf()
                if invoice_url:
                    logger.info("✅ Facture générée : %s", invoice_url)
                    return invoice_url
                else:
                    logger.error("❌ Échec génération facture contrat #%s", contract.id)
                    return None
            return contract.invoice_url
        except Exception as e:
            logger.error("❌ Erreur vérification facture contrat #%s : %s", contract.id, e)
            return None

    def perform_create(self, serializer):
        receipt = serializer.save(created_by=self.request.user)

        if receipt.contract and receipt.next_due_date:
            PaymentReceipt.objects.filter(
                contract=receipt.contract,
            ).exclude(pk=receipt.pk).update(next_due_date=None)

        receipt.generate_pdf()

        if receipt.contract:
            threading.Thread(
                target=self._check_and_generate_invoice,
                args=(receipt.contract,),
                daemon=True
            ).start()

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        try:
            amount = Decimal(data.get("amount", "0"))
        except Exception:
            return Response({"error": "Montant invalide."}, status=400)

        if amount <= 0:
            return Response({"error": "Le montant doit être supérieur à zéro."}, status=400)

        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        old_receipt_url = instance.receipt_url

        response = super().update(request, *args, **kwargs)

        if response.status_code == 200:
            changed_fields = set(request.data.keys())
            if changed_fields & FIELDS_THAT_REQUIRE_RECEIPT_PDF_REGEN:
                instance.refresh_from_db()

                if old_receipt_url:
                    try:
                        self._delete_file_from_url("receipts", old_receipt_url)
                    except Exception as e:
                        logger.warning("Impossible de supprimer l'ancien reçu PDF: %s", e)

                PaymentReceipt.objects.filter(pk=instance.pk).update(receipt_url=None)
                instance.receipt_url = None
                instance.generate_pdf()
                instance.refresh_from_db()

                return Response(self.get_serializer(instance).data)

        return response

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        old_receipt_url = instance.receipt_url

        response = super().partial_update(request, *args, **kwargs)

        if response.status_code == 200:
            changed_fields = set(request.data.keys())
            if changed_fields & FIELDS_THAT_REQUIRE_RECEIPT_PDF_REGEN:
                instance.refresh_from_db()

                if old_receipt_url:
                    try:
                        self._delete_file_from_url("receipts", old_receipt_url)
                    except Exception as e:
                        logger.warning("Impossible de supprimer l'ancien reçu PDF: %s", e)

                PaymentReceipt.objects.filter(pk=instance.pk).update(receipt_url=None)
                instance.receipt_url = None
                instance.generate_pdf()
                instance.refresh_from_db()

                return Response(self.get_serializer(instance).data)

        return response

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.receipt_url:
            try:
                self._delete_file_from_url("receipts", instance.receipt_url)
            except Exception as e:
                logger.warning("Erreur suppression reçu PDF S3 : %s", e)
        return super().destroy(request, *args, **kwargs)

    def _delete_file_from_url(self, bucket_key: str, file_url: str):
        try:
            from django.conf import settings
            from api.utils.cloud.scw.bucket_utils import delete_object

            bucket = settings.SCW_BUCKETS[bucket_key]
            split_token = f"/{bucket}/"
            path = file_url.split(split_token, 1)[-1]
            delete_object(bucket_key, path)
        except Exception as e:
            logger.error("Erreur suppression fichier S3: %s", e)
            raise

    @action(detail=False, methods=["post"], url_path="send-email")
    def send_receipts_email(self, request):
        lead_id = request.data.get("lead_id")
        receipt_ids = request.data.get("receipt_ids", [])

        if not lead_id or not receipt_ids:
            return Response(
                {"detail": "lead_id et receipt_ids sont requis."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            receipt_ids = [int(rid) for rid in receipt_ids]
        except (ValueError, TypeError):
            return Response({"detail": "receipt_ids doit contenir des entiers."}, status=400)

        try:
            lead = Lead.objects.get(pk=lead_id)
        except Lead.DoesNotExist:
            return Response({"detail": "Lead introuvable."}, status=404)

        if not lead.email:
            return Response({"detail": "Ce lead ne possède pas d'adresse email."}, status=400)

        receipts = PaymentReceipt.objects.filter(id__in=receipt_ids, client__lead=lead)
        if not receipts.exists():
            return Response({"detail": "Aucun reçu trouvé pour ce lead."}, status=404)

        from api.leads_events.models import LeadEvent
        from api.leads.automation.handlers.receipt_sent import handle_receipts_email_sent

        event = LeadEvent.log(
            lead=lead,
            event_code="RECEIPTS_EMAIL_SENT",
            actor=request.user,
            data={"receipt_ids": receipt_ids},
        )

        handle_receipts_email_sent(event)

        return Response({"detail": "📨 Envoi des reçus en cours."}, status=200)

    @action(detail=False, methods=["get"], url_path="upcoming")
    def upcoming_payments(self, request):
        today = date.today()

        receipts = (
            PaymentReceipt.objects
            .filter(next_due_date__gte=today)
            .select_related("contract", "client__lead")
            .order_by("contract_id", "next_due_date")
        )

        grouped = defaultdict(list)
        for r in receipts:
            if r.contract and r.contract.balance_due > 0:
                grouped[r.contract.id].append(r)

        unique_receipts = [r_list[0] for r_list in grouped.values()]

        results = []
        for receipt in unique_receipts:
            results.append({
                "receipt_id": receipt.id,
                "contract_id": receipt.contract.id,
                "client_id": receipt.client.id,
                "first_name": receipt.client.lead.first_name,
                "last_name": receipt.client.lead.last_name,
                "phone": receipt.client.lead.phone,
                "next_due_date": receipt.next_due_date,
                "balance_due": str(receipt.contract.balance_due),
                "service_details": str(receipt.contract.service)
            })

        results.sort(key=lambda r: r["next_due_date"])
        return Response(results)

    @action(detail=True, methods=["patch"], url_path="update-due-date")
    def update_next_due_date(self, request, pk=None):
        try:
            receipt = self.get_object()
        except PaymentReceipt.DoesNotExist:
            return Response({"detail": "Reçu introuvable."}, status=404)

        new_date = request.data.get("next_due_date")
        if not new_date:
            return Response({"next_due_date": "Ce champ est requis."}, status=400)

        try:
            parsed_date = datetime.fromisoformat(new_date).date()
        except ValueError:
            return Response({
                "next_due_date": "Format invalide. Utilisez YYYY-MM-DD ou YYYY-MM-DDTHH:MM."
            }, status=400)

        receipt.next_due_date = parsed_date
        receipt.save(update_fields=["next_due_date"])

        # ✅ Django-Q2 : appel direct (plus de .delay())
        try:
            send_due_date_updated_email_task(receipt.id, parsed_date.isoformat())
        except Exception as e:
            logger.exception("Erreur lors de l'envoi de l'email de mise à jour de l'échéance.")

        return Response({
            "receipt_id": receipt.id,
            "contract_id": receipt.contract.id if receipt.contract else None,
            "client": str(receipt.client),
            "new_next_due_date": parsed_date,
        })