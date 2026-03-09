from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from apps.core.views import service_worker

urlpatterns = [
    path('service-worker.js', service_worker, name='service_worker'),
    path('admin/', admin.site.urls),
    path('', include('apps.website.urls')),
    path('app/', include('apps.core.urls')),
    path('crm/', include('apps.crm.urls')),
    path('pos/', include('apps.pos.urls')),
    path('logistics/', include('apps.logistics.urls')),
    path('accounting/', include('apps.accounting.urls')),
    path('sales/', include('apps.sales.urls')),
    path('manufacturing/', include('apps.manufacturing.urls')),
    path('sunat/', include('apps.sunat_integration.urls')),
    path('api/', include('apps.core.api_urls')),
    path('api/n8n/', include('apps.n8n_integration.urls')),
]

if settings.ENVIRONMENT == 'testing':
    urlpatterns.insert(1, path('accounts/', include('allauth.urls')))

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
