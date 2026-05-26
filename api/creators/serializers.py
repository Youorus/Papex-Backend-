from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from api.creators.models import CreatorProfile, SocialAccountLead, PromoCode, CreatorContract
from api.users.roles import UserRoles

User = get_user_model()


class CreatorProfileSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField(source="user.id", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)
    full_name = serializers.CharField(source="user.get_full_name", read_only=True)
    is_active = serializers.BooleanField(source="user.is_active", read_only=True)

    class Meta:
        model = CreatorProfile
        fields = (
            "id",
            "user_id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "is_active",
            "phone_number",
            "country",
            "city",
            "currency",
            "status",
            "notes",
            "created_at",
            "updated_at",
        )


class CreatorProfileCreateSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(write_only=True)
    first_name = serializers.CharField(write_only=True)
    last_name = serializers.CharField(write_only=True)
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        style={"input_type": "password"},
    )

    class Meta:
        model = CreatorProfile
        fields = (
            "email",
            "first_name",
            "last_name",
            "password",
            "phone_number",
            "country",
            "city",
            "currency",
            "notes",
        )

    def validate_email(self, value):
        email = value.strip().lower()
        if User.objects.filter(email=email).exists():
            raise ValidationError("Un utilisateur avec cet email existe déjà.")
        return email

    @transaction.atomic
    def create(self, validated_data):
        user_data = {
            "email": validated_data.pop("email"),
            "first_name": validated_data.pop("first_name"),
            "last_name": validated_data.pop("last_name"),
            "password": validated_data.pop("password"),
        }

        user = User.objects.create_user(**user_data, role=UserRoles.CREATOR)
        return CreatorProfile.objects.create(user=user, **validated_data)


class CreatorProfileUpdateSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source="user.first_name", required=False)
    last_name = serializers.CharField(source="user.last_name", required=False)
    is_active = serializers.BooleanField(source="user.is_active", required=False)

    class Meta:
        model = CreatorProfile
        fields = (
            "first_name",
            "last_name",
            "phone_number",
            "country",
            "city",
            "currency",
            "status",
            "notes",
            "is_active",
        )

    @transaction.atomic
    def update(self, instance, validated_data):
        user_data = validated_data.pop("user", {})
        user = instance.user

        if user_data:
            for attr, value in user_data.items():
                setattr(user, attr, value)
            user.save(update_fields=list(user_data.keys()))

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance


class CreatorMiniSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    full_name = serializers.CharField(source="user.get_full_name", read_only=True)

    class Meta:
        model = CreatorProfile
        fields = (
            "id",
            "email",
            "full_name",
            "status",
            "currency",
        )


class CreatorContractSerializer(serializers.ModelSerializer):
    creator = CreatorMiniSerializer(read_only=True)
    creator_id = serializers.UUIDField(write_only=True, source="creator")

    class Meta:
        model = CreatorContract
        fields = (
            "id",
            "title",
            "file",
            "creator",
            "creator_id",
            "created_at",
            "updated_at",
        )


class PromoCodeSerializer(serializers.ModelSerializer):
    creator = CreatorMiniSerializer(read_only=True)
    creator_id = serializers.UUIDField(write_only=True, source="creator")

    class Meta:
        model = PromoCode
        fields = (
            "id",
            "creator",
            "creator_id",
            "code",
            "status",
            "commission_rate",
            "bonus_amount",
            "description",
            "valid_until",
            "created_at",
            "updated_at",
        )

    def validate_code(self, value):
        code = value.strip().upper()
        queryset = PromoCode.objects.filter(code=code)

        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise ValidationError("Ce code promotionnel est déjà utilisé.")

        return code


class SocialAccountLeadSerializer(serializers.ModelSerializer):
    creator = CreatorMiniSerializer(read_only=True)

    class Meta:
        model = SocialAccountLead
        fields = (
            "id",
            "platform",
            "username",
            "display_name",
            "profile_url",
            "followers_count",
            "bio",
            "country",
            "language",
            "categories",
            "source",
            "is_viable",
            "contact_status",
            "creator",
            "notes",
            "raw_data",
            "created_at",
            "updated_at",
        )


class SocialAccountLeadCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialAccountLead
        fields = (
            "platform",
            "username",
            "display_name",
            "profile_url",
            "followers_count",
            "bio",
            "country",
            "language",
            "categories",
            "source",
            "is_viable",
            "contact_status",
            "creator",
            "notes",
            "raw_data",
        )

    def validate_username(self, value):
        return value.strip().lstrip("@")

    def validate_profile_url(self, value):
        return value.strip() if value else value


class CreatorKpiSerializer(serializers.Serializer):
    """
    Serializer pour les indicateurs de performance (KPIs) d'un créateur.
    """
    total_leads = serializers.IntegerField(read_only=True)
    total_contracts = serializers.IntegerField(read_only=True)
    conversion_rate = serializers.FloatField(read_only=True)
    total_revenue = serializers.DecimalField(read_only=True, max_digits=12, decimal_places=2)
    total_commissions = serializers.DecimalField(read_only=True, max_digits=12, decimal_places=2)
    currency = serializers.CharField(read_only=True)


class CreatorAggregateKpiSerializer(CreatorKpiSerializer):
    """
    Serializer pour les KPIs agrégés, incluant les informations du créateur.
    """
    id = serializers.UUIDField(source="creator_id")
    full_name = serializers.CharField(source="creator_full_name")
    currency = serializers.CharField(source="creator_currency")

    class Meta:
        fields = (
            "id",
            "full_name",
            "total_leads",
            "total_contracts",
            "conversion_rate",
            "total_revenue",
            "total_commissions",
            "currency",
        )