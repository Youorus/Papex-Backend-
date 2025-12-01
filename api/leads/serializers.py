from datetime import datetime
from zoneinfo import ZoneInfo

import phonenumbers
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from api.clients.serializers import ClientSerializer
from api.lead_status.models import LeadStatus
from api.lead_status.serializer import LeadStatusSerializer
from api.leads.constants import RDV_CONFIRME, RDV_PLANIFIE
from api.leads.models import Lead
from api.statut_dossier.models import StatutDossier
from api.statut_dossier.serializers import StatutDossierSerializer
from api.statut_dossier_interne.models import StatutDossierInterne
from api.statut_dossier_interne.serializers import StatutDossierInterneSerializer
from api.users.assigned_user_serializer import AssignedUserSerializer
from api.users.models import User
from api.users.roles import UserRoles

EUROPE_PARIS = ZoneInfo("Europe/Paris")

# Les codes de statuts qui nécessitent obligatoirement un RDV (à adapter si besoin)
STATUSES_REQUIRING_APPOINTMENT = {RDV_CONFIRME, RDV_PLANIFIE}

"""
Sérialiseur principal pour le modèle Lead.

Gère la validation, la sérialisation et la désérialisation des données liées à un lead,
y compris les relations avec les statuts, les juristes, les conseillers et les données du client.

Comporte également une validation métier spécifique : certains statuts nécessitent obligatoirement
une date de rendez-vous, et les emails doivent être uniques.

Formatte la date du rendez-vous selon le fuseau Europe/Paris.
"""


class LeadSerializer(serializers.ModelSerializer):
    appointment_date = serializers.DateTimeField(
        input_formats=["%d/%m/%Y %H:%M"],
        default_timezone=EUROPE_PARIS,
        format="%d/%m/%Y %H:%M",
        allow_null=True,
        required=False,
    )
    form_data = ClientSerializer(read_only=True)
    assigned_to = AssignedUserSerializer(read_only=True, many=True)
    status = LeadStatusSerializer(read_only=True)
    statut_dossier = StatutDossierSerializer(read_only=True)
    jurist_assigned = AssignedUserSerializer(read_only=True, many=True)
    jurist_assigned_ids = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role=UserRoles.JURISTE, is_active=True),
        many=True,
        source="jurist_assigned",
        write_only=True,
        required=False,
    )

    status_id = serializers.PrimaryKeyRelatedField(
        queryset=LeadStatus.objects.all(),
        source="status",
        write_only=True,
        required=False,
    )
    statut_dossier_id = serializers.PrimaryKeyRelatedField(
        queryset=StatutDossier.objects.all(),
        source="statut_dossier",
        write_only=True,
        required=False,
    )
    assigned_to_ids = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role=UserRoles.CONSEILLER, is_active=True),
        many=True,
        source="assigned_to",
        write_only=True,
        required=False,
    )
    statut_dossier_interne = StatutDossierInterneSerializer(read_only=True)
    statut_dossier_interne_id = serializers.PrimaryKeyRelatedField(
        queryset=StatutDossierInterne.objects.all(),
        source="statut_dossier_interne",
        write_only=True,
        required=False,
    )

    contract_emitter_id = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = [
            "id",
            "first_name",
            "last_name",
            "email",
            "phone",
            "appointment_date",
            "created_at",
            "form_data",
            "status",
            "status_id",
            "assigned_to",
            "assigned_to_ids",
            "contract_emitter_id",
            "statut_dossier",
            "statut_dossier_id",
            "statut_dossier_interne",
            "statut_dossier_interne_id",
            "jurist_assigned",
            "jurist_assigned_ids",
        ]
        extra_kwargs = {
            "first_name": {
                "allow_blank": False,
                "error_messages": {
                    "blank": "Le prénom est requis",
                    "required": "Le prénom est requis",
                },
            },
            "last_name": {
                "allow_blank": False,
                "error_messages": {
                    "blank": "Le nom est requis",
                    "required": "Le nom est requis",
                },
            },
            "phone": {
                "allow_blank": False,
                "error_messages": {
                    "blank": "Le numéro de téléphone est requis",
                    "required": "Le numéro de téléphone est requis",
                },
            },
            "email": {
                "allow_blank": False,
                "error_messages": {
                    "blank": "L'email est requis",
                    "required": "L'email est requis",
                },
            },
            "created_at": {"read_only": True},
        }

    def get_contract_emitter_id(self, obj):
        client = getattr(obj, "form_data", None)
        if not client:
            return None
        contract = getattr(client, "contracts", None)
        if contract is not None:
            contract = contract.order_by("-created_at").first()
            if contract and contract.created_by:
                return str(contract.created_by.id)
        return None

    def validate_email(self, value):
        if not value:
            raise serializers.ValidationError("L'email est requis")
        if "@" not in value:
            raise serializers.ValidationError(
                "Veuillez entrer une adresse email valide"
            )
        email = value.lower().strip()
        # Unicité
        if self.instance:  # Update
            if (
                Lead.objects.exclude(pk=self.instance.pk)
                .filter(email__iexact=email)
                .exists()
            ):
                raise serializers.ValidationError(
                    "Cet email est déjà utilisé par un autre utilisateur, veuillez nous contacter."
                )
        else:  # Create
            if Lead.objects.filter(email__iexact=email).exists():
                raise serializers.ValidationError(
                    "Cet email est déjà utilisé par un autre utilisateur, veuillez nous contacter."
                )
        return email

    def validate_first_name(self, value):
        if not value:
            raise serializers.ValidationError("Le prénom est requis")
        return value.capitalize()

    def validate_last_name(self, value):
        if not value:
            raise serializers.ValidationError("Le nom est requis")
        return value.capitalize()

    def validate_phone(self, value):
        if not value:
            raise serializers.ValidationError("Le numéro de téléphone est requis")
        return value

    def validate(self, data):
        status = data.get("status") or getattr(self.instance, "status", None)
        appointment_date = data.get("appointment_date") or getattr(
            self.instance, "appointment_date", None
        )
        # Validation métier pour statut nécessitant un rendez-vous
        if status and hasattr(status, "code"):
            if status.code in STATUSES_REQUIRING_APPOINTMENT and not appointment_date:
                raise serializers.ValidationError(
                    {
                        "appointment_date": f"Une date de rendez-vous est requise pour ce statut «{status.label}»."
                    }
                )
        return super().validate(data)

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        if instance.appointment_date:
            # Convertit l'UTC stockée en Europe/Paris
            paris_dt = instance.appointment_date.astimezone(EUROPE_PARIS)
            rep["appointment_date"] = paris_dt.strftime("%d/%m/%Y %H:%M")
        if instance.status:
            rep["status_display"] = instance.status.label
        return rep
