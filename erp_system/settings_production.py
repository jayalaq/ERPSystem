"""
Production settings - extends base settings with security hardening,
Cloudflare R2 storage, and PostgreSQL configuration.
"""
from .settings import *  # noqa: F401, F403
import os

# =============================================================================
# SECURITY
# =============================================================================
DEBUG = False
SECRET_KEY = os.environ['SECRET_KEY']
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(',')

# Cloudflare handles SSL termination, trust CF-Visitor header
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
# Cloudflare already redirects HTTP->HTTPS; Django must not redirect
# again or it creates an infinite loop (nginx $scheme is always 'http')
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'SAMEORIGIN'

SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 28800  # 8 hours
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
CSRF_TRUSTED_ORIGINS = [
    f"https://{host.strip()}" for host in ALLOWED_HOSTS if host.strip()
]

# =============================================================================
# DATABASE - PostgreSQL (production)
# =============================================================================
import dj_database_url
DATABASES = {
    'default': dj_database_url.parse(
        os.environ['DATABASE_URL'],
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# =============================================================================
# CACHE - Redis
# =============================================================================
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', 'redis://redis:6379/0'),
        'KEY_PREFIX': 'erp',
        'TIMEOUT': 300,
    }
}

SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'

# =============================================================================
# CLOUDFLARE R2 STORAGE
# =============================================================================
USE_R2_STORAGE = bool(os.environ.get('CLOUDFLARE_R2_ACCESS_KEY'))

if USE_R2_STORAGE:
    STORAGES = {
        'default': {
            'BACKEND': 'erp_system.storage_backends.MediaR2Storage',
        },
        'staticfiles': {
            'BACKEND': 'erp_system.storage_backends.StaticR2Storage',
        },
    }
else:
    STORAGES = {
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
        },
        'staticfiles': {
            'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
        },
    }

# =============================================================================
# CELERY (background tasks: SUNAT, emails, reports)
# =============================================================================
CELERY_BROKER_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 300  # 5 minutes max per task
CELERY_BEAT_SCHEDULE = {
    'check-overdue-invoices': {
        'task': 'apps.accounting.tasks.check_overdue_invoices',
        'schedule': 86400.0,  # Daily
    },
    'update-exchange-rate': {
        'task': 'apps.sunat_integration.tasks.update_exchange_rate',
        'schedule': 43200.0,  # Every 12 hours
    },
    'backup-reminder': {
        'task': 'apps.core.tasks.send_backup_reminder',
        'schedule': 604800.0,  # Weekly
    },
    'n8n-daily-summary': {
        'task': 'apps.n8n_integration.tasks.send_daily_summary',
        'schedule': 86400.0,  # Daily
    },
    'n8n-retry-failed-webhooks': {
        'task': 'apps.n8n_integration.tasks.retry_failed_webhooks',
        'schedule': 3600.0,  # Every hour
    },
}

# =============================================================================
# EMAIL
# =============================================================================
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER)

# =============================================================================
# LOGGING
# =============================================================================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'apps': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps.sunat_integration': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# =============================================================================
# REST FRAMEWORK (tighter for production)
# =============================================================================
REST_FRAMEWORK['DEFAULT_THROTTLE_CLASSES'] = [
    'rest_framework.throttling.AnonRateThrottle',
    'rest_framework.throttling.UserRateThrottle',
]
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {
    'anon': '20/minute',
    'user': '200/minute',
}

# =============================================================================
# CORS (production - restrict to your domain)
# =============================================================================
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = CSRF_TRUSTED_ORIGINS
