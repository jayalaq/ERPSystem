from django.contrib import admin
from .models import Customer, CustomerContact, Supplier, Opportunity, Interaction


class CustomerContactInline(admin.TabularInline):
    model = CustomerContact
    extra = 1


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['doc_number', 'name', 'customer_type', 'phone', 'email', 'is_active']
    list_filter = ['customer_type', 'doc_type', 'is_active']
    search_fields = ['name', 'doc_number', 'email']
    inlines = [CustomerContactInline]


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ['doc_number', 'name', 'phone', 'email', 'is_active']
    search_fields = ['name', 'doc_number']


@admin.register(Opportunity)
class OpportunityAdmin(admin.ModelAdmin):
    list_display = ['title', 'customer', 'stage', 'expected_amount', 'probability', 'assigned_to']
    list_filter = ['stage', 'priority']


@admin.register(Interaction)
class InteractionAdmin(admin.ModelAdmin):
    list_display = ['subject', 'customer', 'interaction_type', 'date', 'performed_by']
    list_filter = ['interaction_type']
