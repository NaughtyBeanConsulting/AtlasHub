from django.contrib import admin
from django.shortcuts import redirect
from unfold.admin import ModelAdmin

from .models import WhatsAppDevice, WhatsAppMessage


@admin.register(WhatsAppMessage)
class WhatsAppMessageAdmin(ModelAdmin):
    list_display = ['phone_number', 'user', 'message_type', 'status', 'retry_count', 'created_at', 'sent_at']
    list_filter = ['status', 'message_type']
    search_fields = ['phone_number', 'message', 'user__email']
    readonly_fields = ['created_at', 'sent_at']


@admin.register(WhatsAppDevice)
class WhatsAppDeviceAdmin(ModelAdmin):
    """Sidebar 'Connection' entry that jumps to the ops dashboard."""

    def changelist_view(self, request, extra_context=None):
        return redirect('whatsapp:dashboard')

    def has_add_permission(self, request):
        return False
