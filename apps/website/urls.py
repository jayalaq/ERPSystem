from django.urls import path
from . import views

app_name = 'website'

urlpatterns = [
    path('', views.landing_page, name='landing'),
    path('contacto/', views.contact_submit, name='contact_submit'),
]
