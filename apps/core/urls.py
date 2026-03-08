from django.conf import settings
from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('health/', views.health_check, name='health_check'),
]

if settings.ENVIRONMENT == 'testing':
    urlpatterns += [
        path('login/google/', views.google_login_redirect, name='google_login'),
    ]
