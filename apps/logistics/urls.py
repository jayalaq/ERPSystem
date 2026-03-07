from django.urls import path
from . import views

app_name = 'logistics'

urlpatterns = [
    path('products/', views.product_list, name='product_list'),
    path('products/new/', views.product_create, name='product_create'),
    path('products/<int:pk>/edit/', views.product_edit, name='product_edit'),
    path('warehouses/', views.warehouse_list, name='warehouse_list'),
    path('inventory/', views.inventory_view, name='inventory'),
    path('movements/', views.stock_movement_list, name='movement_list'),
    path('movements/new/', views.stock_movement_create, name='movement_create'),
    path('purchase-orders/', views.purchase_order_list, name='purchase_order_list'),
    path('purchase-orders/new/', views.purchase_order_create, name='purchase_order_create'),
]
