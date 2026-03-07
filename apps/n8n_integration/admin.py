from django.contrib import admin
from .models import N8nWebhook, N8nEventLog, N8nIncomingAction


@admin.register(N8nWebhook)
class N8nWebhookAdmin(admin.ModelAdmin):
    list_display = ['name', 'event_type', 'webhook_url', 'is_active', 'retry_count']
    list_filter = ['event_type', 'is_active']
    search_fields = ['name', 'webhook_url']


@admin.register(N8nEventLog)
class N8nEventLogAdmin(admin.ModelAdmin):
    list_display = ['event_type', 'webhook', 'status', 'response_code', 'attempts', 'created_at']
    list_filter = ['status', 'event_type']
    readonly_fields = ['webhook', 'event_type', 'payload', 'status', 'response_code',
                       'response_body', 'error_message', 'attempts', 'created_at', 'sent_at']


@admin.register(N8nIncomingAction)
class N8nIncomingActionAdmin(admin.ModelAdmin):
    list_display = ['action_type', 'source', 'success', 'n8n_execution_id', 'created_at']
    list_filter = ['action_type', 'success']
    readonly_fields = ['action_type', 'source', 'payload', 'result', 'success',
                       'error_message', 'n8n_execution_id', 'created_at']
