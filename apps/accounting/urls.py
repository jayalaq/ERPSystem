from django.urls import path
from . import views

app_name = 'accounting'

urlpatterns = [
    path('invoices/', views.invoice_list, name='invoice_list'),
    path('invoices/new/', views.invoice_create, name='invoice_create'),
    path('invoices/<int:pk>/', views.invoice_detail, name='invoice_detail'),
    path('invoices/<int:pk>/send-sunat/', views.invoice_send_sunat, name='invoice_send_sunat'),
    path('payments/new/', views.payment_create, name='payment_create'),
    path('accounts-payable/', views.accounts_payable, name='accounts_payable'),
    path('document-series/', views.document_series_list, name='document_series'),
    path('document-series/new/', views.document_series_create, name='document_series_create'),
    path('reports/', views.reports_dashboard, name='reports'),
]
