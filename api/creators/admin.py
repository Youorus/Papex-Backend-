from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from api.creators.models import CreatorProfile, SocialAccountLead, PromoCode


@admin.register(CreatorProfile)
class CreatorProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "status",
        "country",
        "city",
        "created_at",
    )
    search_fields = ("user__email", "user__first_name", "user__last_name")
    list_filter = ("status", "country", "created_at")


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "creator",
        "status",
        "commission_rate",
        "bonus_amount",
        "valid_until",
        "created_at",
    )
    search_fields = ("code", "creator__user__email", "creator__user__first_name")
    list_filter = ("status", "created_at", "valid_until")
    autocomplete_fields = ("creator",)


@admin.register(SocialAccountLead)
class SocialAccountLeadAdmin(admin.ModelAdmin):
    list_display = (
        "platform",
        "username",
        "followers_count",
        "is_viable",
        "contact_status",
        "creator",
        "created_at",
    )
    search_fields = ("username", "profile_url", "notes")
    list_filter = ("platform", "contact_status", "is_viable", "created_at")
    autocomplete_fields = ("creator",)
