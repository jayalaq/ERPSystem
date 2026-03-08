from django.contrib import admin
from .models import BillOfMaterials, BOMComponent, ProductionOrder, ProductionOrderComponent


class BOMComponentInline(admin.TabularInline):
    model = BOMComponent
    extra = 1


@admin.register(BillOfMaterials)
class BillOfMaterialsAdmin(admin.ModelAdmin):
    list_display = ['product', 'name', 'bom_type', 'estimated_cost', 'is_active']
    list_filter = ['bom_type', 'is_active']
    search_fields = ['product__name', 'name']
    inlines = [BOMComponentInline]


class ProductionOrderComponentInline(admin.TabularInline):
    model = ProductionOrderComponent
    extra = 0


@admin.register(ProductionOrder)
class ProductionOrderAdmin(admin.ModelAdmin):
    list_display = ['number', 'product', 'quantity', 'status', 'priority', 'planned_date']
    list_filter = ['status', 'priority']
    search_fields = ['number', 'product__name']
    inlines = [ProductionOrderComponentInline]
