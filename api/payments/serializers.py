from decimal import Decimal

from rest_framework import serializers

from api.payments.enums import PaymentMode
from api.payments.models import PaymentReceipt
from api.utils.cloud.scw.bucket_utils import generate_presigned_url


class PaymentReceiptSerializer(serializers.ModelSerializer):
    contract_id = serializers.IntegerField(source="contract.id", read_only=True)
    contract_service = serializers.CharField(source="contract.service", read_only=True)
    receipt_url = serializers.SerializerMethodField()

    class Meta:
        model = PaymentReceipt
        fields = [
            "id",
            "client",
            "contract",
            "contract_id",
            "contract_service",
            "mode",
            "payment_date",
            "receipt_url",
            "amount",
            "created_by",
            "next_due_date",
        ]
        read_only_fields = [
            "id",
            "contract_id",
            "contract_service",
            "receipt_url",
            "created_by",
        ]

    def validate_amount(self, value):
        if value <= Decimal("0.00"):
            raise serializers.ValidationError("Le montant doit être supérieur à zéro.")
        return value

    def validate_mode(self, value):
        if value not in PaymentMode.values:
            raise serializers.ValidationError("Mode de paiement invalide.")
        return value

    def get_receipt_url(self, obj):
        """
        Retourne une URL signée temporaire pour consulter un reçu PDF.
        Si `receipt_url` est une URL complète, on en extrait uniquement la key S3.
        """
        if obj.receipt_url:
            from urllib.parse import unquote, urlparse

            parsed = urlparse(obj.receipt_url)
            path = unquote(parsed.path)  # Ex: /recus/junior_marc_2/recu_2_20250901.pdf
            key = "/".join(path.strip("/").split("/")[1:])  # Retire le préfixe "recus/"
            return generate_presigned_url("receipts", key)
        return None
