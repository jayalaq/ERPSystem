from django.contrib import admin
from .models import ContactMessage


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'service_interest', 'status', 'created_at']
    list_filter = ['status', 'service_interest', 'created_at']
    search_fields = ['name', 'email', 'company']
    readonly_fields = ['ip_address', 'created_at']
    list_editable = ['status']
