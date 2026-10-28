from pathlib import Path
import dj_database_url
from decouple import Config, RepositoryEnv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from backend/.env
env_path = BASE_DIR / '.env'
config = Config(RepositoryEnv(str(env_path))) if env_path.exists() else Config(os.environ)

SECRET_KEY = config('DJANGO_SECRET_KEY', default='django-insecure-collivra-backend-secret-key-1234567890')
DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
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
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True

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
DATABASE_URL = config('DATABASE_URL')
DATABASES = {
    'default': dj_database_url.config(
        default=DATABASE_URL,
        conn_max_age=0,
        ssl_require=True,
    )
}
# Disable server-side cursors to ensure full compatibility with PgBouncer Transaction Pooling
DATABASES['default']['DISABLE_SERVER_SIDE_CURSORS'] = True

# Supabase Configurations
SUPABASE_URL = config('SUPABASE_URL', default='https://eetmsobqxlbsvcoscjnb.supabase.co')
SUPABASE_ANON_KEY = config('SUPABASE_ANON_KEY', default='')
SUPABASE_SERVICE_ROLE_KEY = config('SUPABASE_SERVICE_ROLE_KEY', default='')
SUPABASE_JWT_SECRET = config('SUPABASE_JWT_SECRET', default='')

DEV_MODE = config('DEV_MODE', default=True, cast=bool)
SHOW_SEED_DATA = config('SHOW_SEED_DATA', default=True, cast=bool)
FIELD_ENCRYPTION_KEY = config('FIELD_ENCRYPTION_KEY', default='0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef')

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'api.authentication.SupabaseAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'UNAUTHENTICATED_USER': None,
}

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
