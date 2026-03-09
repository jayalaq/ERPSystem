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
    path('cotizaciones/<int:pk>/firmar/', views.quotation_sign, name='quotation_sign'),
    path('cotizaciones/<int:pk>/nota/', views.quotation_add_note, name='quotation_add_note'),
    path('cotizaciones/<int:pk>/pdf/', views.quotation_pdf, name='quotation_pdf'),

    # Sales Orders
    path('pedidos/', views.order_list, name='order_list'),
    path('pedidos/nuevo/', views.order_create, name='order_create'),
    path('pedidos/<int:pk>/', views.order_detail, name='order_detail'),
    path('pedidos/<int:pk>/editar/', views.order_edit, name='order_edit'),
    path('pedidos/<int:pk>/agregar-item/', views.order_add_item, name='order_add_item'),
    path('pedidos/<int:pk>/eliminar-item/<int:item_pk>/', views.order_remove_item, name='order_remove_item'),
    path('pedidos/<int:pk>/confirmar/', views.order_confirm, name='order_confirm'),
    path('pedidos/<int:pk>/generar-picking/', views.order_generate_picking, name='order_generate_picking'),
    path('pedidos/<int:pk>/nota/', views.order_add_note, name='order_add_note'),

    # Picking
    path('picking/', views.picking_list, name='picking_list'),
    path('picking/<int:pk>/', views.picking_detail, name='picking_detail'),
    path('picking/<int:pk>/iniciar/', views.picking_start, name='picking_start'),
    path('picking/<int:pk>/preparar-item/<int:item_pk>/', views.picking_pick_item, name='picking_pick_item'),

    # Price Lists
    path('listas-precio/', views.price_list_list, name='price_list_list'),
    path('listas-precio/nueva/', views.price_list_create, name='price_list_create'),
    path('listas-precio/<int:pk>/', views.price_list_detail, name='price_list_detail'),
    path('listas-precio/<int:pk>/editar/', views.price_list_edit, name='price_list_edit'),
    path('listas-precio/<int:pk>/agregar-item/', views.price_list_add_item, name='price_list_add_item'),
    path('listas-precio/<int:pk>/eliminar-item/<int:item_pk>/', views.price_list_remove_item, name='price_list_remove_item'),

    # Payment Terms
    path('terminos-pago/', views.payment_term_list, name='payment_term_list'),
    path('terminos-pago/nuevo/', views.payment_term_create, name='payment_term_create'),
    path('terminos-pago/<int:pk>/', views.payment_term_detail, name='payment_term_detail'),
    path('terminos-pago/<int:pk>/editar/', views.payment_term_edit, name='payment_term_edit'),
    path('terminos-pago/<int:pk>/agregar-cuota/', views.payment_term_add_installment, name='payment_term_add_installment'),
    path('terminos-pago/<int:pk>/eliminar-cuota/<int:inst_pk>/', views.payment_term_remove_installment, name='payment_term_remove_installment'),

    # API
    path('api/product-price/', views.api_get_product_price, name='api_product_price'),
]
