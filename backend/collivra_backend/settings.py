import os
from pathlib import Path
import dj_database_url
from decouple import AutoConfig

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from backend/.env or system environment
config = AutoConfig(search_path=str(BASE_DIR))

SECRET_KEY = config('DJANGO_SECRET_KEY', default='django-insecure-collivra-backend-secret-key-1234567890')
DEBUG = config('DEBUG', default=True, cast=bool)
raw_hosts = config('ALLOWED_HOSTS', default='')
ALLOWED_HOSTS = [h.strip() for h in raw_hosts.split(',') if h.strip()]

NUM_PROXIES = config('NUM_PROXIES', default=1, cast=int)

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.postgres',
    'corsheaders',
    'rest_framework',
    'api',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'api.errors.JsonErrorMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# CORS Configuration
raw_cors = config('CORS_ALLOWED_ORIGINS', default='')
CORS_ALLOWED_ORIGINS = [o.strip() for o in raw_cors.split(',') if o.strip()]
CORS_ALLOW_CREDENTIALS = False

ROOT_URLCONF = 'collivra_backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'collivra_backend.wsgi.application'

# Database configuration connecting via Supabase Transaction Pooler (port 6543)
DATABASE_URL = config('DATABASE_URL', default='sqlite:///:memory:')
DATABASES = {
    'default': dj_database_url.config(
        default=DATABASE_URL,
        conn_max_age=0,
        ssl_require=DATABASE_URL.startswith('postgres'),
    )
}
# Disable server-side cursors to ensure full compatibility with PgBouncer Transaction Pooling
if DATABASE_URL.startswith('postgres'):
    DATABASES['default']['DISABLE_SERVER_SIDE_CURSORS'] = True

# Supabase Configurations
SUPABASE_URL = config('SUPABASE_URL', default='https://eetmsobqxlbsvcoscjnb.supabase.co')
SUPABASE_ANON_KEY = config('SUPABASE_ANON_KEY', default='')
SUPABASE_SERVICE_ROLE_KEY = config('SUPABASE_SERVICE_ROLE_KEY', default='')
SUPABASE_JWT_SECRET = config('SUPABASE_JWT_SECRET', default='')

DEV_MODE = config('DEV_MODE', default=True, cast=bool)
SHOW_SEED_DATA = config('SHOW_SEED_DATA', default=False, cast=bool)
FIELD_ENCRYPTION_KEY = config('FIELD_ENCRYPTION_KEY', default='0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef')

# Twilio Verify Configuration
TWILIO_ACCOUNT_SID = config('TWILIO_ACCOUNT_SID', default='')
TWILIO_AUTH_TOKEN = config('TWILIO_AUTH_TOKEN', default='')
TWILIO_VERIFY_SERVICE_SID = config('TWILIO_VERIFY_SERVICE_SID', default='')

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'api.authentication.SupabaseAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '60/min',
        'user': '120/min',
        'login': '5/min',
        'otp_send': '5/hour',
        'email_otp_send': '5/hour',
        'signup': '10/hour',
    },
    'NUM_PROXIES': NUM_PROXIES,
    'EXCEPTION_HANDLER': 'api.errors.custom_exception_handler',
    'UNAUTHENTICATED_USER': None,
}

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Email / SMTP Configuration
EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default=EMAIL_HOST_USER or 'Collivra <no-reply@collivra.app>')

