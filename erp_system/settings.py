import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-dev-key-change-in-production')
DEBUG = os.environ.get('DEBUG', 'True').lower() in ('true', '1', 'yes')
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
CSRF_TRUSTED_ORIGINS = [
    f"https://{host.strip()}" for host in ALLOWED_HOSTS if host.strip()
]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'django.contrib.sites',
    # Third party
    'rest_framework',
    'corsheaders',
    'django_filters',
    'crispy_forms',
    'crispy_bootstrap5',
    # Allauth (Google OAuth)
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    # Local apps
    'apps.core',
    'apps.crm',
    'apps.pos',
    'apps.logistics',
    'apps.accounting',
    'apps.sunat_integration',
    'apps.n8n_integration',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'erp_system.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.core.context_processors.company_info',
            ],
        },
    },
]

WSGI_APPLICATION = 'erp_system.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Use PostgreSQL in production
if os.environ.get('DATABASE_URL'):
    import dj_database_url
    DATABASES['default'] = dj_database_url.parse(os.environ['DATABASE_URL'])

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'es-pe'
TIME_ZONE = 'America/Lima'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'core.User'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 25,
}

CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK = 'bootstrap5'

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/login/'

# Django Sites Framework (required by allauth)
SITE_ID = 1

# Allauth Configuration
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

ACCOUNT_LOGIN_METHODS = {'username'}
ACCOUNT_EMAIL_VERIFICATION = 'none'
ACCOUNT_SIGNUP_ENABLED = False
ACCOUNT_ADAPTER = 'apps.core.adapters.NoNewUsersAccountAdapter'
SOCIALACCOUNT_ADAPTER = 'apps.core.adapters.GoogleOnlyLoginAdapter'
SOCIALACCOUNT_LOGIN_ON_GET = True
SOCIALACCOUNT_AUTO_SIGNUP = False
ACCOUNT_DEFAULT_HTTP_PROTOCOL = os.environ.get('ACCOUNT_DEFAULT_HTTP_PROTOCOL', 'http')

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
        'APP': {
            'client_id': os.environ.get('GOOGLE_CLIENT_ID', ''),
            'secret': os.environ.get('GOOGLE_CLIENT_SECRET', ''),
        },
    },
}

# SUNAT Configuration
SUNAT_CONFIG = {
    'RUC': os.environ.get('SUNAT_RUC', ''),
    'USER': os.environ.get('SUNAT_USER', 'MODDATOS'),
    'PASSWORD': os.environ.get('SUNAT_PASSWORD', 'moddatos'),
    'CLIENT_ID': os.environ.get('SUNAT_CLIENT_ID', ''),
    'CLIENT_SECRET': os.environ.get('SUNAT_CLIENT_SECRET', ''),
    'PRODUCTION': os.environ.get('SUNAT_PRODUCTION', 'False').lower() == 'true',
    'BETA_URL': 'https://e-beta.sunat.gob.pe/ol-ti-itcpfegem-beta/billService',
    'PRODUCTION_URL': 'https://e-factura.sunat.gob.pe/ol-ti-itcpfegem/billService',
    'CONSULT_RUC_URL': 'https://api.apis.net.pe/v2/sunat/ruc',
    'TIPO_CAMBIO_URL': 'https://api.apis.net.pe/v2/sunat/tipo-cambio',
}

# Company Configuration
COMPANY_CONFIG = {
    'NAME': os.environ.get('COMPANY_NAME', 'Mi Empresa SAC'),
    'RUC': os.environ.get('COMPANY_RUC', '20123456789'),
    'ADDRESS': os.environ.get('COMPANY_ADDRESS', 'Lima, Peru'),
    'PHONE': os.environ.get('COMPANY_PHONE', ''),
    'EMAIL': os.environ.get('COMPANY_EMAIL', ''),
    'WEBSITE': os.environ.get('COMPANY_WEBSITE', ''),
    'LOGO': os.environ.get('COMPANY_LOGO', ''),
    'IGV_RATE': 0.18,
    'CURRENCY': 'PEN',
}

CORS_ALLOW_ALL_ORIGINS = DEBUG

# n8n Integration
N8N_WEBHOOK_URL = os.environ.get('N8N_WEBHOOK_URL', 'http://n8n:5678')
N8N_API_KEY = os.environ.get('N8N_API_KEY', '')
