import logging
from decimal import Decimal
from collections import defaultdict
import threading
from concurrent.futures import ThreadPoolExecutor

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from datetime import date, timedelta
from datetime import datetime

from api.leads.models import Lead
from api.payments.models import PaymentReceipt
from api.payments.permissions import IsPaymentEditor
from api.payments.serializers import PaymentReceiptSerializer
from api.utils.cloud.scw.bucket_utils import delete_object
from api.utils.email.recus.tasks import send_receipts_email_task
from api.utils.email.recus.tasks import send_due_date_updated_email_task

logger = logging.getLogger(__name__)


class PaymentReceiptViewSet(viewsets.ModelViewSet):
    """
    API ViewSet pour gérer les reçus de paiement (PaymentReceipt).
    """

    serializer_class = PaymentReceiptSerializer
    permission_classes = [IsPaymentEditor]

    def get_queryset(self):
        """
        Permet de filtrer les paiements par contract_id.
        """
        queryset = PaymentReceipt.objects.select_related("client", "contract", "created_by")

        contract_id = self.request.query_params.get("contract_id")

        if contract_id:
            queryset = queryset.filter(contract_id=contract_id)

        return queryset.order_by("-payment_date")

    def _check_and_generate_invoice(self, contract):
        """
        Vérifie si le contrat est entièrement payé et génère la facture si c'est le cas.
        """
        try:
            # Rafraîchir le contrat depuis la base pour avoir les données à jour
            contract.refresh_from_db()

            if contract.is_fully_paid and not contract.invoice_url:
                logger.info(f"🎉 Contrat #{contract.id} entièrement payé, génération de la facture...")

                # Générer la facture PDF
                invoice_url = contract.generate_invoice_pdf()

                if invoice_url:
                    logger.info(f"✅ Facture générée avec succès: {invoice_url}")
                    return invoice_url
                else:
                    logger.error(f"❌ Échec de la génération de la facture pour le contrat #{contract.id}")
                    return None
            else:
                if contract.invoice_url:
                    logger.debug(f"ℹ️ Facture déjà générée pour le contrat #{contract.id}")
                elif not contract.is_fully_paid:
                    logger.debug(
                        f"ℹ️ Contrat #{contract.id} pas encore entièrement payé (solde: {contract.balance_due}€)")

                return contract.invoice_url

        except Exception as e:
            logger.error(f"❌ Erreur lors de la vérification/génération de la facture pour contrat #{contract.id}: {e}")
            return None

    def perform_create(self, serializer):
        """
        Sauvegarde le reçu avec l'utilisateur connecté, puis génère son PDF.
        Écrase aussi les autres `next_due_date` pour ce contrat.
        """
        receipt = serializer.save(created_by=self.request.user)

        # Si une prochaine échéance est définie, on l'unifie
        if receipt.contract and receipt.next_due_date:
            PaymentReceipt.objects.filter(
                contract=receipt.contract,
            ).exclude(
                pk=receipt.pk
            ).update(next_due_date=None)

        # Générer le PDF du reçu
        receipt.generate_pdf()

        # ✅ VÉRIFIER SI C'EST LE DERNIER PAIEMENT ET GÉNÉRER LA FACTURE
        if receipt.contract:
            # Lancer la vérification dans un thread séparé pour ne pas bloquer la réponse
            threading.Thread(
                target=self._check_and_generate_invoice,
                args=(receipt.contract,),
                daemon=True
            ).start()

    def create(self, request, *args, **kwargs):
        """
        Empêche la création si le montant est ≤ 0.
        """
        data = request.data.copy()
        try:
            amount = Decimal(data.get("amount", "0"))
        except Exception:
            return Response({"error": "Montant invalide."}, status=400)

        if amount <= 0:
            return Response(
                {"error": "Le montant doit être supérieur à zéro."}, status=400
            )

        return super().create(request, *args, **kwargs)

    def _regenerate_pdf_async(self, receipt_id, old_receipt_url=None):
        """
        Régénère le PDF de manière asynchrone dans un thread séparé.
        """

        def regenerate_task():
            try:
                logger.info(f"Début régénération PDF asynchrone pour reçu #{receipt_id}")

                # ✅ IMPORTANT: Récupérer une NOUVELLE instance depuis la base
                from api.payments.models import PaymentReceipt
                receipt = PaymentReceipt.objects.get(id=receipt_id)

                # Supprimer l'ancien PDF s'il existe
                if old_receipt_url:
                    try:
                        self._delete_file_from_url("receipts", old_receipt_url)
                        logger.info(f"Ancien PDF supprimé: {old_receipt_url}")
                    except Exception as e:
                        logger.warning(f"Impossible de supprimer l'ancien PDF: {e}")

                # ✅ Générer le PDF avec les NOUVELLES données
                receipt.generate_pdf()
                logger.info(f"PDF régénéré avec succès pour reçu #{receipt_id}")

            except PaymentReceipt.DoesNotExist:
                logger.error(f"Reçu #{receipt_id} introuvable")
            except Exception as e:
                logger.error(f"Erreur régénération PDF asynchrone reçu #{receipt_id}: {e}")

        # Lancer dans un thread séparé
        import threading
        thread = threading.Thread(target=regenerate_task)
        thread.daemon = True
        thread.start()

    def update(self, request, *args, **kwargs):
        """
        Surcharge de la méthode update avec régénération asynchrone du PDF.
        """
        instance = self.get_object()

        # Sauvegarde de l'ancienne URL pour suppression potentielle
        old_receipt_url = instance.receipt_url

        # Appel de la méthode update normale
        response = super().update(request, *args, **kwargs)

        # Si la mise à jour a réussi, on lance la régénération asynchrone
        if response.status_code == 200:
            try:
                # ✅ RAFRAÎCHIR l'instance depuis la base pour avoir les nouvelles données
                instance.refresh_from_db()

                # Lancer la régénération asynchrone
                self._regenerate_pdf_async(instance.id, old_receipt_url)
                logger.info(f"Régénération PDF asynchrone lancée pour reçu #{instance.id}")

            except Exception as e:
                logger.error(f"Erreur lancement régénération asynchrone: {e}")

        return response

    def partial_update(self, request, *args, **kwargs):
        """
        Surcharge de partial_update avec la même logique asynchrone.
        """
        instance = self.get_object()
        old_receipt_url = instance.receipt_url

        response = super().partial_update(request, *args, **kwargs)

        if response.status_code == 200:
            try:
                # ✅ RAFRAÎCHIR l'instance depuis la base
                instance.refresh_from_db()

                self._regenerate_pdf_async(instance.id, old_receipt_url)
                logger.info(f"Régénération PDF asynchrone lancée pour reçu #{instance.id}")

            except Exception as e:
                logger.error(f"Erreur lancement régénération asynchrone: {e}")

        return response

    def destroy(self, request, *args, **kwargs):
        """
        Supprime aussi le PDF dans S3 (Scaleway/MinIO) si présent.
        """
        instance = self.get_object()
        if instance.receipt_url:
            try:
                self._delete_file_from_url("receipts", instance.receipt_url)
            except Exception as e:
                logger.warning(f"Erreur suppression du reçu PDF S3 : {e}")
        return super().destroy(request, *args, **kwargs)

    def _delete_file_from_url(self, bucket_key: str, file_url: str):
        """
        Supprime un fichier du storage à partir de son URL.
        """
        try:
            from django.conf import settings
            from api.utils.cloud.scw.bucket_utils import delete_object

            bucket = settings.SCW_BUCKETS[bucket_key]
            split_token = f"/{bucket}/"
            path = file_url.split(split_token, 1)[-1]
            delete_object(bucket_key, path)
        except Exception as e:
            logger.error(f"Erreur suppression fichier S3: {e}")
            raise

    @action(detail=False, methods=["post"], url_path="send-email")
    def send_receipts_email(self, request):
        """
        Envoie un ou plusieurs reçus PDF par email au lead concerné.

        Expects: {
            "lead_id": int,
            "receipt_ids": [int, ...]
        }
        """
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
            return Response(
                {"detail": "receipt_ids doit contenir des entiers."}, status=400
            )

        try:
            lead = Lead.objects.get(pk=lead_id)
        except Lead.DoesNotExist:
            return Response({"detail": "Lead introuvable."}, status=404)

        if not lead.email:
            return Response(
                {"detail": "Ce lead ne possède pas d'adresse email."}, status=400
            )

        receipts = PaymentReceipt.objects.filter(id__in=receipt_ids, client__lead=lead)
        if not receipts.exists():
            return Response({"detail": "Aucun reçu trouvé pour ce lead."}, status=404)

        try:
            send_receipts_email_task.delay(lead.id)
        except Exception as e:
            logger.exception(
                "Erreur lors du déclenchement de la task d'envoi des reçus."
            )
            return Response({"detail": f"Erreur technique : {str(e)}"}, status=500)

        return Response(
            {"detail": "Envoi des reçus programmé avec succès."}, status=200
        )

    @action(detail=False, methods=["get"], url_path="upcoming")
    def upcoming_payments(self, request):
        """
        Retourne la liste des paiements à venir (next_due_date ≥ aujourd'hui),
        en ne retenant qu'un seul reçu par contrat (le plus proche),
        pour les contrats avec un solde dû, triés par date croissante.

        SANS FILTRE sur l'utilisateur : accessible à tous les utilisateurs autorisés.
        """
        today = date.today()

        # Étape 1 : requête initiale SANS filtre sur created_by
        receipts = (
            PaymentReceipt.objects
            .filter(
                next_due_date__gte=today,
            )
            .select_related("contract", "client__lead")
            .order_by("contract_id", "next_due_date")
        )

        # Étape 2 : filtrer pour ne garder que le reçu le plus proche par contrat
        grouped = defaultdict(list)
        for r in receipts:
            if r.contract and r.contract.balance_due > 0:
                grouped[r.contract.id].append(r)

        # Étape 3 : ne garder que le premier reçu (le plus proche) pour chaque contrat
        unique_receipts = [r_list[0] for r_list in grouped.values()]

        # Étape 4 : construction de la réponse
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

        # Trier les résultats finaux par date d'échéance
        results.sort(key=lambda r: r["next_due_date"])

        return Response(results)

    @action(detail=True, methods=["patch"], url_path="update-due-date")
    def update_next_due_date(self, request, pk=None):
        """
        Met à jour la prochaine date d'échéance d'un reçu lié à un contrat.
        """
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
                "next_due_date": "Format de date invalide. Utilisez YYYY-MM-DD ou YYYY-MM-DDTHH:MM."
            }, status=400)

        receipt.next_due_date = parsed_date
        receipt.save(update_fields=["next_due_date"])

        try:
            send_due_date_updated_email_task.delay(receipt.id, parsed_date.isoformat())
        except Exception as e:
            logger.exception("Erreur lors de l'envoi de l'email de mise à jour de l'échéance.")

        return Response({
            "receipt_id": receipt.id,
            "contract_id": receipt.contract.id if receipt.contract else None,
            "client": str(receipt.client),
            "new_next_due_date": parsed_date,
        })