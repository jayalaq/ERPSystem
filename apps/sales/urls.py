from django.urls import path
from . import views

app_name = 'sales'

urlpatterns = [
    # Quotations
    path('cotizaciones/', views.quotation_list, name='quotation_list'),
    path('cotizaciones/nueva/', views.quotation_create, name='quotation_create'),
    path('cotizaciones/<int:pk>/', views.quotation_detail, name='quotation_detail'),
    path('cotizaciones/<int:pk>/editar/', views.quotation_edit, name='quotation_edit'),
    path('cotizaciones/<int:pk>/agregar-item/', views.quotation_add_item, name='quotation_add_item'),
    path('cotizaciones/<int:pk>/eliminar-item/<int:item_pk>/', views.quotation_remove_item, name='quotation_remove_item'),
    path('cotizaciones/<int:pk>/convertir/', views.quotation_convert_to_order, name='quotation_convert_to_order'),

    # Sales Orders
    path('pedidos/', views.order_list, name='order_list'),
    path('pedidos/nuevo/', views.order_create, name='order_create'),
    path('pedidos/<int:pk>/', views.order_detail, name='order_detail'),
    path('pedidos/<int:pk>/editar/', views.order_edit, name='order_edit'),
    path('pedidos/<int:pk>/agregar-item/', views.order_add_item, name='order_add_item'),
    path('pedidos/<int:pk>/eliminar-item/<int:item_pk>/', views.order_remove_item, name='order_remove_item'),
    path('pedidos/<int:pk>/confirmar/', views.order_confirm, name='order_confirm'),
    path('pedidos/<int:pk>/generar-picking/', views.order_generate_picking, name='order_generate_picking'),

    # Picking
    path('picking/', views.picking_list, name='picking_list'),
    path('picking/<int:pk>/', views.picking_detail, name='picking_detail'),
    path('picking/<int:pk>/iniciar/', views.picking_start, name='picking_start'),
    path('picking/<int:pk>/preparar-item/<int:item_pk>/', views.picking_pick_item, name='picking_pick_item'),
]
