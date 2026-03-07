from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.crm.api import CustomerViewSet, SupplierViewSet, OpportunityViewSet
from apps.logistics.api import ProductViewSet, WarehouseViewSet, StockLevelViewSet
from apps.accounting.api import InvoiceViewSet
from apps.pos.api import POSSaleViewSet

router = DefaultRouter()
router.register(r'customers', CustomerViewSet)
router.register(r'suppliers', SupplierViewSet)
router.register(r'opportunities', OpportunityViewSet)
router.register(r'products', ProductViewSet)
router.register(r'warehouses', WarehouseViewSet)
router.register(r'stock-levels', StockLevelViewSet)
router.register(r'invoices', InvoiceViewSet)
router.register(r'pos-sales', POSSaleViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
