from django.urls import path
from . import views

app_name = 'n8n'

urlpatterns = [
    # Actions (n8n → ERP)
    path('action/', views.n8n_action, name='action'),

    # Data queries (n8n reads from ERP)
    path('customers/', views.n8n_customers, name='customers'),
    path('products/', views.n8n_products, name='products'),
    path('stock/', views.n8n_stock, name='stock'),
    path('sales/', views.n8n_sales, name='sales'),
    path('invoices/', views.n8n_invoices, name='invoices'),
    path('opportunities/', views.n8n_opportunities, name='opportunities'),
    path('dashboard/', views.n8n_dashboard, name='dashboard'),
    path('logs/', views.n8n_event_logs, name='logs'),
]
