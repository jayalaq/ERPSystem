from django.conf import settings
from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('health/', views.health_check, name='health_check'),
    path('video-tutorials/', views.video_tutorials, name='video_tutorials'),
    path('system-customize/', views.system_customize, name='system_customize'),
    path('feature-flags/', views.feature_flags_config, name='feature_flags'),
]

if settings.ENVIRONMENT == 'testing':
    urlpatterns += [
        path('login/google/', views.google_login_redirect, name='google_login'),
    ]
