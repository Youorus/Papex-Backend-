import logging
from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from django.db.models import Sum, DecimalField, Value
from decimal import Decimal
from api.clients.models import Client
from api.clients.permissions import IsClientCreateOpen
from api.clients.serializers import ClientSerializer
from api.leads.models import Lead
from api.leads.serializers import LeadSerializer
from api.contracts.models import Contract
from api.contracts.serializer import ContractSerializer
from api.contracts.contract_search import ContractSearchService
from api.utils.cloud.scw.deletion import cleanup_client_cascade_s3

logger = logging.getLogger(__name__)


class ClientViewSet(viewsets.ModelViewSet):
    queryset = Client.objects.select_related("lead")
    serializer_class = ClientSerializer
    permission_classes = [IsClientCreateOpen]

    # ─────────────────────────────
    # CREATE / UPSERT CLIENT
    # ─────────────────────────────
    def perform_create(self, serializer):
        """
        Crée ou met à jour un client lié à un lead.
        """
        lead_id = self.request.query_params.get("id")

        # 🔥 création simple
        if not lead_id:
            return serializer.save()

        # 🔎 récupération lead
        try:
            lead = Lead.objects.get(pk=lead_id)
        except Lead.DoesNotExist:
            raise ValidationError({"lead": "Lead introuvable avec cet ID."})

        # 🔁 UPSERT client
        existing_client = Client.objects.filter(lead=lead).first()

        if existing_client:
            serializer.instance = existing_client
            return serializer.save()

        return serializer.save(lead=lead)

    def create(self, request, *args, **kwargs):
        """
        Override pour gérer le mode partiel depuis un lead
        """
        lead_id = request.query_params.get("id")

        if lead_id:
            serializer = self.get_serializer(
                data=request.data,
                context={"skip_type_demande_validation": True},
                partial=True,
            )
            serializer.is_valid(raise_exception=True)
            client = self.perform_create(serializer)

            return Response(
                ClientSerializer(client).data,
                status=status.HTTP_200_OK,
            )

        return super().create(request, *args, **kwargs)

    # ─────────────────────────────
    # 🔥 NOUVEL ENDPOINT CONTRACTS
    # ─────────────────────────────
    from django.db.models import Sum, DecimalField, Value
    from decimal import Decimal

    @action(detail=True, methods=["get"], url_path="contracts")
    def contracts(self, request, pk=None):
        """
        Retourne tous les contrats d'un client
        """
        client = self.get_object()

        qs = (
            Contract.objects
            .filter(client=client)
            .select_related("service", "created_by")
            .prefetch_related("receipts")
            .annotate(
                amount_paid_annotated=Sum(
                    "receipts__amount",
                    output_field=DecimalField(max_digits=10, decimal_places=2),
                    default=Value(Decimal("0.00")),
                )
            )
        )

        serializer = ContractSerializer(qs, many=True)
        return Response(serializer.data)

    # ─────────────────────────────
    # CASCADE DELETE
    # ─────────────────────────────
    @action(detail=False, methods=["delete"], url_path="cascade-delete-by-lead")
    def cascade_delete_by_lead(self, request):
        """
        Supprime un lead et toute sa cascade :
        - Fichiers S3
        - Client
        - Relations
        """
        lead_id = request.query_params.get("lead_id")

        if not lead_id:
            return Response(
                {"detail": "lead_id manquant."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        logger.info(f"🗑️ [CASCADE DELETE] Lead #{lead_id}")

        # 🔎 récupérer lead
        try:
            lead = Lead.objects.get(pk=lead_id)
        except Lead.DoesNotExist:
            logger.warning(f"⚠️ Lead #{lead_id} introuvable")
            return Response(
                {"detail": "Lead introuvable."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # sauvegarde data (si besoin audit)
        lead_data = LeadSerializer(lead).data

        # 🔥 récupérer client AVANT delete
        client = Client.objects.filter(lead=lead).first()

        s3_stats = {
            "documents": 0,
            "contracts": 0,
            "receipts": 0,
            "clients": 0,
            "total": 0,
        }

        # 🔥 nettoyage S3
        if client:
            logger.info(f"🔥 Nettoyage S3 pour Client #{client.pk}...")
            s3_stats = cleanup_client_cascade_s3(client)
        else:
            logger.warning(f"⚠️ Aucun client trouvé pour Lead #{lead_id}")

        # 🔥 suppression DB
        with transaction.atomic():
            lead.delete()

        logger.info(
            f"✅ Lead #{lead_id} supprimé | {s3_stats['total']} fichiers S3 "
            f"(docs: {s3_stats['documents']}, contrats: {s3_stats['contracts']}, "
            f"reçus: {s3_stats['receipts']})"
        )

        return Response(status=status.HTTP_200_OK)