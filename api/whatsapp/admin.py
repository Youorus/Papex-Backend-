# api/whatsapp/admin.py
from django.contrib import admin
from .models import WhatsAppMessage


@admin.register(WhatsAppMessage)
class WhatsAppMessageAdmin(admin.ModelAdmin):
    list_display  = ("lead", "sender_phone", "short_body", "is_outbound", "is_read", "delivery_status", "timestamp")
    list_filter   = ("is_outbound", "is_read", "delivery_status")
    search_fields = ("sender_phone", "body", "lead__first_name", "lead__last_name")
    readonly_fields = ("wa_id", "timestamp")
    ordering      = ("-timestamp",)

    def short_body(self, obj):
        return obj.body[:60] + ("…" if len(obj.body) > 60 else "")
    short_body.short_description = "Message"
