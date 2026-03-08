from django.urls import path
from . import views

app_name = 'manufacturing'

urlpatterns = [
    # Bill of Materials
    path('bom/', views.bom_list, name='bom_list'),
    path('bom/nueva/', views.bom_create, name='bom_create'),
    path('bom/<int:pk>/', views.bom_detail, name='bom_detail'),
    path('bom/<int:pk>/editar/', views.bom_edit, name='bom_edit'),
    path('bom/<int:pk>/agregar-componente/', views.bom_add_component, name='bom_add_component'),
    path('bom/<int:pk>/eliminar-componente/<int:comp_pk>/', views.bom_remove_component, name='bom_remove_component'),

    # Production Orders
    path('ordenes/', views.production_order_list, name='production_order_list'),
    path('ordenes/nueva/', views.production_order_create, name='production_order_create'),
    path('ordenes/<int:pk>/', views.production_order_detail, name='production_order_detail'),
    path('ordenes/<int:pk>/confirmar/', views.production_order_confirm, name='production_order_confirm'),
    path('ordenes/<int:pk>/iniciar/', views.production_order_start, name='production_order_start'),
    path('ordenes/<int:pk>/completar/', views.production_order_complete, name='production_order_complete'),
]
