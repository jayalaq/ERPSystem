from django.contrib import admin
from .models import CashRegister, CashSession, POSSale, POSSaleItem, PaymentDetail


@admin.register(CashRegister)
class CashRegisterAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'branch', 'is_active']


class POSSaleItemInline(admin.TabularInline):
    model = POSSaleItem
    extra = 0
    readonly_fields = ['product', 'quantity', 'unit_price', 'discount', 'subtotal', 'igv', 'total']


class PaymentDetailInline(admin.TabularInline):
    model = PaymentDetail
    extra = 0


@admin.register(CashSession)
class CashSessionAdmin(admin.ModelAdmin):
    list_display = ['id', 'cash_register', 'user', 'status', 'opening_amount', 'total_sales', 'opened_at']
    list_filter = ['status', 'cash_register']


@admin.register(POSSale)
class POSSaleAdmin(admin.ModelAdmin):
    list_display = ['series', 'correlative', 'doc_type', 'total', 'payment_method', 'status', 'created_at']
    list_filter = ['doc_type', 'payment_method', 'status']
    inlines = [POSSaleItemInline, PaymentDetailInline]
