from django.urls import path
from . import views

app_name = 'pos'

urlpatterns = [
    path('', views.pos_terminal, name='terminal'),
    path('open-session/', views.open_session, name='open_session'),
    path('close-session/', views.close_session, name='close_session'),
    path('session/<int:pk>/summary/', views.session_summary, name='session_summary'),
    path('process-sale/', views.process_sale, name='process_sale'),
    path('sale/<int:pk>/receipt/', views.sale_receipt, name='sale_receipt'),
    path('history/', views.sales_history, name='sales_history'),
    path('product-search/', views.product_search, name='product_search'),
]
