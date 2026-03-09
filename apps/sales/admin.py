from django.contrib import admin
from .models import (
    SalesQuotation, SalesQuotationItem,
    SalesOrder, SalesOrderItem,
    PickingOrder, PickingOrderItem,
    PriceList, PriceListItem,
    PaymentTerm, PaymentTermInstallment,
    SalesActivityLog,
)


class SalesQuotationItemInline(admin.TabularInline):
    model = SalesQuotationItem
    extra = 1


@admin.register(SalesQuotation)
class SalesQuotationAdmin(admin.ModelAdmin):
    list_display = ['number', 'customer', 'status', 'total', 'issue_date', 'valid_until', 'price_list']
    list_filter = ['status', 'price_list']
    search_fields = ['number', 'customer__name']
    inlines = [SalesQuotationItemInline]


class SalesOrderItemInline(admin.TabularInline):
    model = SalesOrderItem
    extra = 1


@admin.register(SalesOrder)
class SalesOrderAdmin(admin.ModelAdmin):
    list_display = ['number', 'customer', 'status', 'total', 'order_date', 'payment_term']
    list_filter = ['status', 'priority']
    search_fields = ['number', 'customer__name']
    inlines = [SalesOrderItemInline]


class PickingOrderItemInline(admin.TabularInline):
    model = PickingOrderItem
    extra = 1


@admin.register(PickingOrder)
class PickingOrderAdmin(admin.ModelAdmin):
    list_display = ['number', 'sales_order', 'status', 'warehouse', 'assigned_to']
    list_filter = ['status']
    inlines = [PickingOrderItemInline]


class PriceListItemInline(admin.TabularInline):
    model = PriceListItem
    extra = 3


@admin.register(PriceList)
class PriceListAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'currency', 'is_active', 'is_default']
    list_filter = ['is_active', 'currency']
    search_fields = ['name', 'code']
    inlines = [PriceListItemInline]


class PaymentTermInstallmentInline(admin.TabularInline):
    model = PaymentTermInstallment
    extra = 2


@admin.register(PaymentTerm)
class PaymentTermAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'is_active', 'is_immediate', 'total_days']
    list_filter = ['is_active', 'is_immediate']
    search_fields = ['name', 'code']
    inlines = [PaymentTermInstallmentInline]


@admin.register(SalesActivityLog)
class SalesActivityLogAdmin(admin.ModelAdmin):
    list_display = ['title', 'activity_type', 'user', 'quotation', 'order', 'created_at']
    list_filter = ['activity_type']
    search_fields = ['title', 'description']
    readonly_fields = ['created_at']
