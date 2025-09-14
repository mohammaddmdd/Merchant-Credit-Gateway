from pathlib import Path
import os
from datetime import timedelta
from django.core.exceptions import ImproperlyConfigured

def env(name, default=None, required=False, cast=str):
    val = os.getenv(name, default)
    if required and val is None:
        raise ImproperlyConfigured(f"Missing env var: {name}")
    if val is not None and cast is not str:
        if cast is bool:
            return str(val).lower() in ("1", "true", "yes", "on")
        try:
            return cast(val)
        except Exception:
            raise ImproperlyConfigured(f"Invalid cast for env var: {name}={val}")
    return val

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = env('DJANGO_SECRET', 'devsecret')
DEBUG = env('DJANGO_DEBUG', '1') == '1'
ALLOWED_HOSTS = env('DJANGO_ALLOWED_HOSTS', '*').split(',')
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Apps ---
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'django_celery_results',
    'payments',
]

# --- Middleware ---
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [],
    'APP_DIRS': True,
    'OPTIONS': {
        'context_processors': [
            'django.template.context_processors.debug',
            'django.template.context_processors.request',
            'django.contrib.auth.context_processors.auth',
            'django.contrib.messages.context_processors.messages',
        ],
    },
}]

WSGI_APPLICATION = 'core.wsgi.application'


POSTGRES_DB = env("POSTGRES_DB", "walletdb")
POSTGRES_USER = env("POSTGRES_USER", "wallet")
POSTGRES_PASSWORD = env("POSTGRES_PASSWORD", "walletpass")
DB_HOST = env("DB_HOST", "db")
DB_PORT = env("DB_PORT", 5432, cast=int)

CONN_MAX_AGE = env("DB_CONN_MAX_AGE", 0, cast=int)

STATEMENT_TIMEOUT_MS = env("DB_STATEMENT_TIMEOUT_MS", 5000, cast=int)  
CONNECT_TIMEOUT_S = env("DB_CONNECT_TIMEOUT_S", 3, cast=int)           

USE_PGBOUNCER = (DB_HOST.strip().lower() == "pgbouncer")

db_options = {
    # جلوگیری از معطلی طولانی در برقراری اتصال
    'connect_timeout': CONNECT_TIMEOUT_S,
}

if not USE_PGBOUNCER:
    db_options['options'] = f'-c statement_timeout={STATEMENT_TIMEOUT_MS}'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': POSTGRES_DB,
        'USER': POSTGRES_USER,
        'PASSWORD': POSTGRES_PASSWORD,
        'HOST': DB_HOST,
        'PORT': DB_PORT,
        'CONN_MAX_AGE': CONN_MAX_AGE,
        'CONN_HEALTH_CHECKS': True, 
        'OPTIONS': db_options,
    }
}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# --- Static ---
STATIC_URL = 'static/'

# --- DRF / Auth ---
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=env('ACCESS_TOKEN_LIFETIME_MINUTES', 60, cast=int)),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=env('REFRESH_TOKEN_LIFETIME_DAYS', 7, cast=int)),
}

# --- Celery ---
CELERY_BROKER_URL = env('CELERY_BROKER_URL', 'redis://redis:6379/0')
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND', 'redis://redis:6379/1')
CELERY_TASK_ALWAYS_EAGER = False
CELERY_TASK_TIME_LIMIT = 60

INTERNAL_TOKEN = env('INTERNAL_TOKEN', 'ChangeMeInternalToken123')
SETTLEMENT_URL = env('SETTLEMENT_URL', 'http://settlement:9000/api/settlement/withdraw')

REDIS_URL = env('REDIS_URL', 'redis://redis:6379/0')