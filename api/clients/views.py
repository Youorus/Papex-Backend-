import logging
from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from api.clients.models import Client
from api.clients.permissions import IsClientCreateOpen
from api.clients.serializers import ClientSerializer
from api.leads.models import Lead
from api.leads.serializers import LeadSerializer
from api.utils.cloud.scw.deletion import cleanup_client_cascade_s3

logger = logging.getLogger(__name__)


class ClientViewSet(viewsets.ModelViewSet):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    permission_classes = [IsClientCreateOpen]

    def perform_create(self, serializer):
        """
        Crée ou met à jour un client lié à un lead.
        """
        lead_id = self.request.query_params.get("id")
        if not lead_id:
            return serializer.save()

        try:
            lead = Lead.objects.get(pk=lead_id)
        except Lead.DoesNotExist:
            raise ValidationError({"lead": "Lead introuvable avec cet ID."})

        existing_client = Client.objects.filter(lead=lead).first()

        if existing_client:
            serializer.instance = existing_client
            return serializer.save()

        return serializer.save(lead=lead)

    def create(self, request, *args, **kwargs):
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

    @action(detail=False, methods=["delete"], url_path="cascade-delete-by-lead")
    def cascade_delete_by_lead(self, request):
        """
        Supprime un lead et toute sa cascade :
        - Fichiers S3 (contrats, reçus, documents)
        - Client en base
        - Toutes les relations (cascades Django)
        """
        lead_id = request.query_params.get("lead_id")
        if not lead_id:
            return Response(
                {"detail": "lead_id manquant."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        logger.info(f"🗑️ [CASCADE DELETE] Lead #{lead_id}")

        # Vérifier l'existence du lead
        try:
            lead = Lead.objects.get(pk=lead_id)
        except Lead.DoesNotExist:
            logger.warning(f"⚠️ Lead #{lead_id} introuvable")
            return Response(
                {"detail": "Lead introuvable."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Sauvegarder les données avant suppression
        lead_data = LeadSerializer(lead).data

        # ✅ ÉTAPE 1 : Récupérer le client AVANT toute suppression
        client = Client.objects.filter(lead=lead).first()

        s3_stats = {
            'documents': 0,
            'contracts': 0,
            'receipts': 0,
            'clients': 0,
            'total': 0
        }

        # ✅ ÉTAPE 2 : Nettoyer S3 si un client existe
        if client:
            logger.info(f"🔥 Nettoyage S3 pour Client #{client.pk}...")
            s3_stats = cleanup_client_cascade_s3(client)
        else:
            logger.warning(f"⚠️ Aucun client trouvé pour Lead #{lead_id}")

        # ✅ ÉTAPE 3 : Suppression en base (cascade Django)
        with transaction.atomic():
            lead.delete()

        logger.info(
            f"✅ Lead #{lead_id} supprimé | {s3_stats['total']} fichiers S3 "
            f"(docs: {s3_stats['documents']}, contrats: {s3_stats['contracts']}, "
            f"reçus: {s3_stats['receipts']})"
        )

        return Response(
            status=status.HTTP_200_OK,
        )