from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from api.comments.models import Comment
from api.leads.models import Lead


class CommentSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.get_full_name", read_only=True)
    created_at = serializers.DateTimeField(format="%d/%m/%Y %H:%M", read_only=True)
    updated_at = serializers.DateTimeField(format="%d/%m/%Y %H:%M", read_only=True)
    can_edit = serializers.SerializerMethodField()
    lead_id = serializers.IntegerField(write_only=True, required=True)

    class Meta:
        model = Comment
        fields = [
            "id",
            "lead",
            "lead_id",
            "author",
            "author_name",
            "content",
            "created_at",
            "updated_at",
            "can_edit",
        ]
        read_only_fields = ["author", "lead", "created_at", "updated_at"]
        extra_kwargs = {
            "content": {
                "error_messages": {
                    "blank": _("Le contenu du commentaire ne peut pas être vide."),
                    "required": _("Veuillez saisir un contenu pour le commentaire."),
                }
            },
            "lead_id": {
                "error_messages": {"required": _("Veuillez spécifier un lead.")}
            },
        }

    def get_can_edit(self, obj):
        request = self.context.get("request")
        return request and (request.user == obj.author or request.user.is_superuser)

    def validate_lead_id(self, value):
        if not Lead.objects.filter(pk=value).exists():
            raise serializers.ValidationError(_("Lead introuvable."))
        return value

    def validate_content(self, value):
        value = value.strip()
        if len(value) < 3:
            raise serializers.ValidationError(
                _("Le commentaire doit contenir au moins 3 caractères.")
            )
        if len(value) > 2000:
            raise serializers.ValidationError(
                _("Le commentaire ne peut pas dépasser 2000 caractères.")
            )
        return value

    def create(self, validated_data):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(
                {
                    "custom_auth": _(
                        "Authentification requise pour créer un commentaire."
                    )
                },
                code="authentication_failed",
            )

        lead_id = validated_data.pop("lead_id")
        lead = Lead.objects.get(pk=lead_id)

        comment = Comment.objects.create(
            lead=lead, author=request.user, **validated_data
        )
        return comment
