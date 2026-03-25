from decimal import Decimal, InvalidOperation
import logging

from django.utils.text import slugify
from django.db import transaction
from django.db.models import Q
from django.conf import settings
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import APIException

from api.contracts.contract_search import ContractSearchService
from api.contracts.models import Contract
from api.contracts.permissions import IsContractEditor
from api.contracts.serializer import ContractSerializer
from api.utils.email.contracts.tasks import send_contract_email_task
from api.utils.cloud.scw.bucket_utils import delete_object, put_object

logger = logging.getLogger(__name__)
FIELDS_THAT_REQUIRE_PDF_REGEN = {"amount_due", "discount_percent", "service"}

class ContractViewSet(viewsets.ModelViewSet):
    queryset = Contract.objects.select_related("client", "created_by").prefetch_related("receipts")
    serializer_class = ContractSerializer
    permission_classes = [IsContractEditor]

    def get_queryset(self):
        return ContractSearchService.build_base_queryset()

    def list(self, request, *args, **kwargs):
        filters = ContractSearchService.extract_filters_from_request(request)
        search_query = request.query_params.get("search", "").strip()

        qs = self.get_queryset()

        # 🔥 FILTER CLIENT (FIX PRINCIPAL)
        client_id = request.query_params.get("client_id")
        if client_id:
            qs = qs.filter(client_id=client_id)

        # 🔎 SEARCH
        if search_query:
            qs = qs.filter(
                Q(client__lead__first_name__icontains=search_query) |
                Q(client__lead__last_name__icontains=search_query) |
                Q(client__lead__email__icontains=search_query) |
                Q(client__lead__phone__icontains=search_query) |
                Q(id__icontains=search_query)
            )

        # 🎯 FILTERS
        qs = ContractSearchService.apply_filters(qs, filters)

        # 📄 PAGINATION
        try:
            page = max(int(request.query_params.get("page", 1)), 1)
        except:
            page = 1

        page_size = 7
        total = qs.count()

        start = (page - 1) * page_size
        end = start + page_size

        # 📊 AGGREGATES
        aggregates = ContractSearchService.calculate_aggregates(qs)

        # 🔥 slice AVANT serializer
        page_qs = qs[start:end]

        serializer = self.get_serializer(page_qs, many=True)

        return Response({
            "total": total,
            "page": page,
            "page_size": page_size,
            "aggregates": aggregates,
            "items": serializer.data
        })

    # ─────────────────────────────
    # CREATE
    # ─────────────────────────────
    @transaction.atomic
    def perform_create(self, serializer):
        contract = serializer.save(created_by=self.request.user)

        pdf_url = contract.generate_contract_pdf()
        if not pdf_url:
            raise APIException("Impossible de générer le PDF du contrat.")

        contract.contract_url = pdf_url
        contract.save(update_fields=["contract_url"])

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
            logger.error("[ContractViewSet] Erreur log CONTRACT_SIGNED : %s", e)

    # ─────────────────────────────
    # UPDATE
    # ─────────────────────────────


    @transaction.atomic
    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()

        signed_contract = request.FILES.get("signed_contract")
        is_signed = request.data.get("is_signed")
        refund_amount = request.data.get("refund_amount")

        if signed_contract:
            if instance.contract_url:
                self._delete_file_from_url("contracts", instance.contract_url)
            instance.contract_url = self._save_signed_contract_pdf(instance, signed_contract)
            instance.save(update_fields=["contract_url"])

        if is_signed is not None:
            instance.is_signed = str(is_signed).lower() in ["true", "1"]
            instance.save(update_fields=["is_signed"])

        if refund_amount is not None:
            try:
                amount = Decimal(str(refund_amount))
                valid, msg = self._is_valid_refund_amount(instance, amount, False)
                if not valid:
                    return Response({"detail": msg}, status=400)
                instance.refund_amount = amount
                instance.is_refunded = amount > 0
                instance.save(update_fields=["refund_amount", "is_refunded"])
            except (InvalidOperation, TypeError):
                return Response({"detail": "Montant invalide."}, status=400)

        response = super().partial_update(request, *args, **kwargs)

        # ── Régénération PDF si champs métier modifiés ────────
        changed_fields = set(request.data.keys())
        if changed_fields & FIELDS_THAT_REQUIRE_PDF_REGEN:
            instance.refresh_from_db()

            # 1. Supprimer l'ancien PDF du bucket
            if instance.contract_url:
                self._delete_file_from_url("contracts", instance.contract_url)

            # 2. Reset l'URL pour forcer la régénération
            Contract.objects.filter(pk=instance.pk).update(contract_url=None)
            instance.contract_url = None

            # 3. Régénérer
            pdf_url = instance.generate_contract_pdf()
            if not pdf_url:
                raise APIException("Impossible de régénérer le PDF du contrat.")

            # 4. Persister la nouvelle URL
            Contract.objects.filter(pk=instance.pk).update(contract_url=pdf_url)
            instance.contract_url = pdf_url

            # 5. Retourner la réponse avec la nouvelle URL
            serializer = self.get_serializer(instance)
            return Response(serializer.data)

        return response

    # ─────────────────────────────
    # DELETE
    # ─────────────────────────────
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        for receipt in instance.receipts.all():
            if receipt.receipt_url:
                self._delete_file_from_url("receipts", receipt.receipt_url)

        if instance.contract_url:
            self._delete_file_from_url("contracts", instance.contract_url)

        if instance.invoice_url:
            self._delete_file_from_url("invoices", instance.invoice_url)

        return super().destroy(request, *args, **kwargs)

    # ─────────────────────────────
    # ACTIONS
    # ─────────────────────────────
    @action(detail=True, methods=["post"], url_path="cancel", permission_classes=[permissions.IsAdminUser])
    def cancel(self, request, pk=None):
        contract = self.get_object()
        contract.is_cancelled = not contract.is_cancelled
        contract.save(update_fields=["is_cancelled"])
        return Response({"is_cancelled": contract.is_cancelled})

    @action(detail=True, methods=["post"], url_path="refund")
    def refund(self, request, pk=None):
        contract = self.get_object()
        raw_amount = request.data.get("refund_amount")

        try:
            amount = Decimal(str(raw_amount))
        except:
            return Response({"detail": "Montant invalide."}, status=400)

        valid, message = self._is_valid_refund_amount(contract, amount, True)
        if not valid:
            return Response({"detail": message}, status=400)

        contract.refund_amount = (contract.refund_amount or Decimal("0.00")) + amount
        contract.is_refunded = True
        contract.save(update_fields=["refund_amount", "is_refunded"])

        return Response(self.get_serializer(contract).data)

    @action(detail=True, methods=["post"], url_path="send-email")
    def send_email(self, request, pk=None):
        contract = self.get_object()

        from api.leads_events.models import LeadEvent
        from api.leads.automation.handlers.contract_sent import handle_contract_email_sent

        lead = contract.client.lead

        # 🔥 EVENT
        event = LeadEvent.log(
            lead=lead,
            event_code="CONTRACT_EMAIL_SENT",
            actor=request.user,
            data={
                "contract_id": contract.id,
            },
        )

        # 🔥 HANDLER (qui déclenche email)
        handle_contract_email_sent(event)

        return Response(
            {"detail": "📨 Email en cours d'envoi."},
            status=202
        )

    # ─────────────────────────────
    # HELPERS
    # ─────────────────────────────
    def _delete_file_from_url(self, bucket_key: str, file_url: str):
        try:
            bucket = settings.SCW_BUCKETS[bucket_key]
            split_token = f"/{bucket}/"

            if split_token in file_url:
                path = file_url.split(split_token, 1)[-1]
                delete_object(bucket_key, path)
        except Exception as e:
            logger.error("Erreur suppression S3: %s", e)

    def _save_signed_contract_pdf(self, instance, file):
        client_slug = slugify(
            f"{instance.client.lead.last_name}_{instance.client.lead.first_name}"
        )

        filename = f"{client_slug}/contrat_{instance.id}_signed.pdf"

        put_object(
            "contracts",
            filename,
            content=file.read(),
            content_type=file.content_type,
        )

        return f"{settings.AWS_S3_ENDPOINT_URL.rstrip('/')}/{settings.SCW_BUCKETS['contracts']}/{filename}"

    def _is_valid_refund_amount(self, contract, amount: Decimal, is_cumulative=True):
        if amount < 0:
            return False, "Le montant ne peut pas être négatif."

        already_paid = contract.amount_paid or Decimal("0.00")

        max_refundable = (
            already_paid - (contract.refund_amount or Decimal("0.00"))
            if is_cumulative
            else already_paid
        )

        if amount > max_refundable:
            return False, f"Dépasse le montant disponible ({max_refundable} €)."

        return True, ""