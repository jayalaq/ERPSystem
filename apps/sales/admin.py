from django.contrib import admin
from .models import (
    SalesQuotation, SalesQuotationItem,
    SalesOrder, SalesOrderItem,
    PickingOrder, PickingOrderItem,
)


class SalesQuotationItemInline(admin.TabularInline):
    model = SalesQuotationItem
    extra = 1


@admin.register(SalesQuotation)
class SalesQuotationAdmin(admin.ModelAdmin):
    list_display = ['number', 'customer', 'status', 'total', 'issue_date', 'valid_until']
    list_filter = ['status']
    search_fields = ['number', 'customer__name']
    inlines = [SalesQuotationItemInline]


class SalesOrderItemInline(admin.TabularInline):
    model = SalesOrderItem
    extra = 1


@admin.register(SalesOrder)
class SalesOrderAdmin(admin.ModelAdmin):
    list_display = ['number', 'customer', 'status', 'total', 'order_date']
    list_filter = ['status']
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
