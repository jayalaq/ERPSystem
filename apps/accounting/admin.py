from django.contrib import admin
from .models import Invoice, InvoiceItem, PaymentRecord, AccountPayable, DocumentSeries


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1


class PaymentRecordInline(admin.TabularInline):
    model = PaymentRecord
    extra = 0


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['full_number', 'doc_type', 'customer', 'total', 'status', 'issue_date']
    list_filter = ['doc_type', 'status']
    search_fields = ['series', 'customer__name']
    inlines = [InvoiceItemInline, PaymentRecordInline]


@admin.register(AccountPayable)
class AccountPayableAdmin(admin.ModelAdmin):
    list_display = ['supplier', 'invoice_number', 'total', 'paid_amount', 'status', 'due_date']
    list_filter = ['status']


@admin.register(DocumentSeries)
class DocumentSeriesAdmin(admin.ModelAdmin):
    list_display = ['doc_type', 'series', 'next_correlative', 'branch', 'is_active']
