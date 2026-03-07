from django.urls import path
from . import views

app_name = 'sunat'

urlpatterns = [
    path('consult-ruc/', views.consult_ruc, name='consult_ruc'),
    path('send-invoice/<int:invoice_id>/', views.send_invoice, name='send_invoice'),
    path('exchange-rate/', views.exchange_rate, name='exchange_rate'),
    path('logs/', views.sunat_logs, name='logs'),
]
