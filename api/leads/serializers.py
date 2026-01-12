from zoneinfo import ZoneInfo

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from api.clients.serializers import ClientSerializer
from api.lead_status.models import LeadStatus
from api.lead_status.serializer import LeadStatusSerializer
from api.leads.constants import (
    RDV_CONFIRME,
    RDV_PLANIFIE,
    RDV_PRESENTIEL,
    APPOINTMENT_TYPE_CHOICES,
)
from api.leads.models import Lead
from api.statut_dossier.models import StatutDossier
from api.statut_dossier.serializers import StatutDossierSerializer
from api.statut_dossier_interne.models import StatutDossierInterne
from api.statut_dossier_interne.serializers import StatutDossierInterneSerializer
from api.users.assigned_user_serializer import AssignedUserSerializer
from api.users.models import User
from api.users.roles import UserRoles


EUROPE_PARIS = ZoneInfo("Europe/Paris")

# Statuts nécessitant obligatoirement un rendez-vous
STATUSES_REQUIRING_APPOINTMENT = {RDV_CONFIRME, RDV_PLANIFIE}


class LeadSerializer(serializers.ModelSerializer):
    # =====================
    # FIELDS
    # =====================

    appointment_date = serializers.DateTimeField(
        input_formats=["%d/%m/%Y %H:%M"],
        default_timezone=EUROPE_PARIS,
        format="%d/%m/%Y %H:%M",
        allow_null=True,
        required=False,
    )

    appointment_type = serializers.ChoiceField(
        choices=APPOINTMENT_TYPE_CHOICES,
        required=False,
        default=RDV_PRESENTIEL,
    )

    last_reminder_sent = serializers.DateTimeField(
        read_only=True,
        format="%d/%m/%Y %H:%M",
        allow_null=True,
    )

    form_data = ClientSerializer(read_only=True)
    assigned_to = AssignedUserSerializer(read_only=True, many=True)
    jurist_assigned = AssignedUserSerializer(read_only=True, many=True)

    status = LeadStatusSerializer(read_only=True)
    statut_dossier = StatutDossierSerializer(read_only=True)
    statut_dossier_interne = StatutDossierInterneSerializer(read_only=True)

    # =====================
    # WRITE-ONLY IDS
    # =====================

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

    statut_dossier_interne_id = serializers.PrimaryKeyRelatedField(
        queryset=StatutDossierInterne.objects.all(),
        source="statut_dossier_interne",
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

    jurist_assigned_ids = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role=UserRoles.JURISTE, is_active=True),
        many=True,
        source="jurist_assigned",
        write_only=True,
        required=False,
    )

    contract_emitter_id = serializers.SerializerMethodField()

    # =====================
    # META
    # =====================

    class Meta:
        model = Lead
        fields = [
            "id",
            "first_name",
            "last_name",
            "email",
            "phone",
            "appointment_type",
            "appointment_date",
            "last_reminder_sent",
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

    # =====================
    # METHODS
    # =====================

    def get_contract_emitter_id(self, obj):
        client = getattr(obj, "form_data", None)
        if not client:
            return None

        contract_qs = getattr(client, "contracts", None)
        if contract_qs:
            contract = contract_qs.order_by("-created_at").first()
            if contract and contract.created_by:
                return str(contract.created_by.id)
        return None

    # =====================
    # VALIDATIONS
    # =====================

    def validate_email(self, value):
        email = value.lower().strip()

        qs = Lead.objects.filter(email__iexact=email)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise serializers.ValidationError(
                "Cet email est déjà utilisé, veuillez nous contacter."
            )

        return email

    def validate_first_name(self, value):
        return value.capitalize()

    def validate_last_name(self, value):
        return value.capitalize()

    def validate(self, data):
        status = data.get("status") or getattr(self.instance, "status", None)
        appointment_date = data.get("appointment_date") or getattr(
            self.instance, "appointment_date", None
        )

        if status and status.code in STATUSES_REQUIRING_APPOINTMENT and not appointment_date:
            raise serializers.ValidationError(
                {
                    "appointment_date": _(
                        "Une date de rendez-vous est requise pour ce statut."
                    )
                }
            )

        return super().validate(data)

    # =====================
    # REPRESENTATION
    # =====================

    def to_representation(self, instance):
        rep = super().to_representation(instance)

        if instance.appointment_date:
            rep["appointment_date"] = (
                instance.appointment_date
                .astimezone(EUROPE_PARIS)
                .strftime("%d/%m/%Y %H:%M")
            )

        if instance.last_reminder_sent:
            rep["last_reminder_sent"] = (
                instance.last_reminder_sent
                .astimezone(EUROPE_PARIS)
                .strftime("%d/%m/%Y %H:%M")
            )
        else:
            rep["last_reminder_sent"] = None

        rep["status_display"] = (
            instance.status.label if instance.status else None
        )

        rep["appointment_type_display"] = (
            instance.get_appointment_type_display()
            if hasattr(instance, "get_appointment_type_display")
            else None
        )

        return rep
