from django.db import transaction
from django.db.models.signals import post_delete, pre_delete
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from api.clients.models import Client
from api.clients.permissions import IsClientCreateOpen
from api.clients.serializers import ClientSerializer
from api.contracts.models import Contract
from api.documents.models import Document
from api.leads.models import Lead
from api.leads.serializers import LeadSerializer
from api.payments.models import PaymentReceipt
from api.utils.email.clients.tasks import send_client_account_created_task


class ClientViewSet(viewsets.ModelViewSet):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    permission_classes = [IsClientCreateOpen]

    def perform_create(self, serializer):
        """
        Crée ou met à jour un client lié à un lead.
        - Si le lead n'a pas encore de client → création
        - Si un client existe déjà pour ce lead → mise à jour (PATCH)
        """
        lead_id = self.request.query_params.get("id")
        if not lead_id:
            return serializer.save()

        try:
            lead = Lead.objects.get(pk=lead_id)
        except Lead.DoesNotExist:
            raise ValidationError({"lead": "Lead introuvable avec cet ID."})

        # Vérifier si un client existe déjà pour ce lead
        existing_client = Client.objects.filter(lead=lead).first()

        if existing_client:
            # 🔄 Mise à jour du client existant
            serializer.instance = existing_client
            updated_client = serializer.save()
            return updated_client

        # Sinon création
        client = serializer.save(lead=lead)
        send_client_account_created_task.delay(client.id)
        return client

    def create(self, request, *args, **kwargs):
        """
        Surcharge de la création :
        - Si `?id=` fourni → création ou mise à jour liée au lead
        - Sinon, création classique
        """
        lead_id = request.query_params.get("id")
        if lead_id:
            serializer = self.get_serializer(
                data=request.data,
                context={"skip_type_demande_validation": True},
                partial=True,  # ⚡ permet la mise à jour partielle
            )
            serializer.is_valid(raise_exception=True)
            client = self.perform_create(serializer)

            headers = self.get_success_headers(serializer.data)
            return Response(
                ClientSerializer(client).data,  # retourne les données à jour
                status=status.HTTP_200_OK,  # ⚡ 200 si update, 201 si new
                headers=headers,
            )

        return super().create(request, *args, **kwargs)

    @action(detail=False, methods=["delete"], url_path="cascade-delete-by-lead")
    def cascade_delete_by_lead(self, request):
        """
        Supprime un lead et toutes ses données associées en cascade.
        Les signaux Django sont désactivés pendant la suppression pour éviter
        les erreurs de sérialisation sur des instances déjà supprimées.
        """
        lead_id = request.query_params.get("lead_id")
        if not lead_id:
            return Response(
                {"detail": "lead_id manquant."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            lead = Lead.objects.get(pk=lead_id)
        except Lead.DoesNotExist:
            return Response(
                {"detail": "Lead introuvable."},
                status=status.HTTP_404_NOT_FOUND
            )

        # 🔹 Sérialiser AVANT toute suppression pour la notification WebSocket si nécessaire
        lead_data = LeadSerializer(lead).data

        client = getattr(lead, "form_data", None)

        # 🔹 Sauvegarder les receivers actuels pour les restaurer après
        post_delete_receivers_backup = post_delete.receivers[:]
        pre_delete_receivers_backup = pre_delete.receivers[:]

        try:
            with transaction.atomic():
                # 🔹 DÉSACTIVER TOUS LES SIGNAUX de suppression
                post_delete.receivers = []
                pre_delete.receivers = []

                if client:
                    # Supprimer paiements liés aux contrats
                    contracts = Contract.objects.filter(client=client)
                    PaymentReceipt.objects.filter(contract__in=contracts).delete()

                    # Supprimer documents liés au client
                    Document.objects.filter(client=client).delete()

                    # Supprimer contrats et client
                    contracts.delete()
                    client.delete()

                # Supprimer le lead
                lead.delete()

        finally:
            # 🔹 RÉACTIVER TOUS LES SIGNAUX (même en cas d'erreur)
            post_delete.receivers = post_delete_receivers_backup
            pre_delete.receivers = pre_delete_receivers_backup

        # 🔹 Optionnel : Envoyer manuellement la notification WebSocket
        # Si vous voulez notifier via WebSocket après suppression :
        # from api.websocket.signals.leads import _send
        # _send("deleted", lead_data)

        return Response(
            {"detail": f"Lead #{lead_id} et client associé supprimés."},
            status=status.HTTP_204_NO_CONTENT
        )