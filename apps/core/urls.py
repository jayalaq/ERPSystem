from django.conf import settings
from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('health/', views.health_check, name='health_check'),
]

if settings.ENVIRONMENT == 'testing':
    # Testing: landing page at /, Google login
    urlpatterns += [
        path('', views.landing_page, name='landing'),
        path('login/google/', views.google_login_redirect, name='google_login'),
    ]
else:
    # Production: dashboard at /
    urlpatterns += [
        path('', views.dashboard, name='home'),
    ]
