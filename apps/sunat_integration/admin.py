from django.contrib import admin
from .models import SunatLog


@admin.register(SunatLog)
class SunatLogAdmin(admin.ModelAdmin):
    list_display = ['action', 'document_number', 'success', 'response_code', 'created_at']
    list_filter = ['action', 'success']
    readonly_fields = ['action', 'document_type', 'document_number', 'request_data',
                       'response_data', 'response_code', 'success', 'error_message', 'created_at']
