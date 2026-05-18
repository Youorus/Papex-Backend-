from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from api.creators.models import CreatorProfile, SocialAccountLead


@admin.register(CreatorProfile)
class CreatorProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "promo_code",
        "status",
        "country",
        "city",
        "commission_rate",
        "created_at",
    )
    search_fields = ("user__email", "user__first_name", "user__last_name", "promo_code")
    list_filter = ("status", "country", "created_at")



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
