from django.contrib import admin
from .models import (
    Category, Brand, UnitOfMeasure, Product, Warehouse,
    StockLevel, StockMovement, PurchaseOrder, PurchaseOrderItem
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'parent', 'is_active', 'order']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(UnitOfMeasure)
class UnitOfMeasureAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'abbreviation']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['sku', 'name', 'category', 'sale_price', 'purchase_price', 'is_active']
    list_filter = ['product_type', 'category', 'brand', 'is_active']
    search_fields = ['name', 'sku', 'barcode']


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'branch', 'is_default', 'is_active']


@admin.register(StockLevel)
class StockLevelAdmin(admin.ModelAdmin):
    list_display = ['product', 'warehouse', 'quantity', 'reserved']


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ['movement_type', 'product', 'warehouse', 'quantity', 'created_at']
    list_filter = ['movement_type']


class PurchaseOrderItemInline(admin.TabularInline):
    model = PurchaseOrderItem
    extra = 1


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ['number', 'supplier', 'status', 'total', 'order_date']
    list_filter = ['status']
    inlines = [PurchaseOrderItemInline]
