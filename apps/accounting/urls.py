from django.urls import path
from . import views

app_name = 'accounting'

urlpatterns = [
    path('invoices/', views.invoice_list, name='invoice_list'),
    path('invoices/new/', views.invoice_create, name='invoice_create'),
    path('invoices/<int:pk>/', views.invoice_detail, name='invoice_detail'),
    path('invoices/<int:pk>/send-sunat/', views.invoice_send_sunat, name='invoice_send_sunat'),
    path('invoices/<int:pk>/pdf/', views.invoice_download_pdf, name='invoice_pdf'),
    path('invoices/<int:pk>/void/', views.invoice_void, name='invoice_void'),
    path('payments/new/', views.payment_create, name='payment_create'),
    path('accounts-payable/', views.accounts_payable, name='accounts_payable'),
    path('accounts-receivable/', views.accounts_receivable, name='accounts_receivable'),
    path('accounts-receivable/<int:pk>/collect/', views.accounts_receivable_collect, name='accounts_receivable_collect'),
    path('petty-cash/', views.petty_cash, name='petty_cash'),
    path('petty-cash/<int:pk>/', views.petty_cash_detail, name='petty_cash_detail'),
    path('daily-receipt-summary/', views.daily_receipt_summary, name='daily_receipt_summary'),
    path('taxpayers/', views.taxpayer_list, name='taxpayer_list'),
    path('document-series/', views.document_series_list, name='document_series'),
    path('document-series/new/', views.document_series_create, name='document_series_create'),
    path('reports/', views.reports_dashboard, name='reports'),
]
