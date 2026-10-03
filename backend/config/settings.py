import base64
import hashlib
import os
from pathlib import Path
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env', override=False)
def boolean(name, default=False):
    return os.getenv(name, str(default)).lower() in ('true', '1', 'yes')
def csv(name, default):
    return [value.strip() for value in os.getenv(name, default).split(',') if value.strip()]

DEBUG = boolean('DEBUG')
SECRET_KEY = os.getenv('SECRET_KEY', 'development-only-change-this-secret')
TEST_MODE = boolean('TEST_MODE')
PAYMENT_MODE = os.getenv('PAYMENT_MODE', 'manual')
PRODUCT_PRICE = int(os.getenv('PRODUCT_PRICE', '990'))
PAYMENT_QR_PATH = '/pay-qrcode.jpg'
SITE_URL = os.getenv('SITE_URL', '').rstrip('/')
ALLOWED_HOSTS = csv('ALLOWED_HOSTS', 'localhost,127.0.0.1')
CSRF_TRUSTED_ORIGINS = csv('CSRF_TRUSTED_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000')
CODE_LOOKUP_KEY = os.getenv('CODE_LOOKUP_KEY', SECRET_KEY + '-lookup')
CODE_ENCRYPTION_KEY = os.getenv('CODE_ENCRYPTION_KEY', base64.urlsafe_b64encode(hashlib.sha256((SECRET_KEY + '-encryption').encode()).digest()).decode())
if not DEBUG and (SECRET_KEY.startswith('development-only') or not os.getenv('CODE_ENCRYPTION_KEY') or not os.getenv('CODE_LOOKUP_KEY')):
    raise ImproperlyConfigured('Production requires SECRET_KEY, CODE_LOOKUP_KEY and CODE_ENCRYPTION_KEY')

INSTALLED_APPS = [
    'django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes',
    'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles',
    'rest_framework', 'corsheaders', 'apps.catalog', 'apps.checkout',
    'apps.payments', 'apps.access', 'apps.quiz', 'apps.operations',
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware', 'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware', 'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware', 'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware', 'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'DIRS': [BASE_DIR / 'templates'], 'APP_DIRS': True,
    'OPTIONS': {'context_processors': ['django.template.context_processors.debug', 'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth', 'django.contrib.messages.context_processors.messages']}}]
WSGI_APPLICATION = 'config.wsgi.application'
DATABASES = {'default': {'ENGINE': 'django.db.backends.postgresql', 'NAME': os.getenv('DB_NAME', 'paid_quiz'),
    'USER': os.getenv('DB_USER', os.getenv('USER', 'postgres')), 'PASSWORD': os.getenv('DB_PASSWORD', ''),
    'HOST': os.getenv('DB_HOST', 'localhost'), 'PORT': os.getenv('DB_PORT', '5432'), 'CONN_MAX_AGE': 60}}
AUTH_PASSWORD_VALIDATORS = [{'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'}]
LANGUAGE_CODE = 'zh-hans'
TIME_ZONE = 'Asia/Shanghai'
USE_I18N = True
USE_TZ = True
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'}}
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer'],
    'DEFAULT_PARSER_CLASSES': ['rest_framework.parsers.JSONParser'],
    'DEFAULT_AUTHENTICATION_CLASSES': ['config.authentication.ConsumerSessionAuthentication'],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.AllowAny'],
    'EXCEPTION_HANDLER': 'config.exceptions.custom_exception_handler',
    'DEFAULT_THROTTLE_CLASSES': ['rest_framework.throttling.AnonRateThrottle', 'rest_framework.throttling.ScopedRateThrottle'],
    'NUM_PROXIES': 1,
    'DEFAULT_THROTTLE_RATES': {'anon': '300/min', 'access': '20/min', 'orders': '20/min', 'tickets': '20/min'},
}
CORS_ALLOWED_ORIGINS = csv('CORS_ALLOWED_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000')
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = ['accept', 'authorization', 'content-type', 'origin', 'user-agent', 'x-csrftoken', 'x-idempotency-key', 'x-requested-with']
SESSION_COOKIE_AGE = 86400 * 30
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = boolean('COOKIE_SECURE', not DEBUG)
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
CSRF_COOKIE_SAMESITE = 'Lax'
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = boolean('SSL_REDIRECT', False)
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
if not DEBUG:
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False

CELERY_BROKER_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
WECHAT_PAY = {key: os.getenv(env, '') for key, env in {
    'MCHID': 'WECHAT_MCHID', 'APPID': 'WECHAT_APPID', 'API_V3_KEY': 'WECHAT_API_V3_KEY',
    'SERIAL_NO': 'WECHAT_SERIAL_NO', 'PRIVATE_KEY_PATH': 'WECHAT_PRIVATE_KEY_PATH',
    'NOTIFY_URL': 'WECHAT_NOTIFY_URL', 'PLATFORM_CERT_PATH': 'WECHAT_PLATFORM_CERT_PATH',
    'PUBLIC_KEY_PATH': 'WECHAT_PUBLIC_KEY_PATH', 'PUBLIC_KEY_ID': 'WECHAT_PUBLIC_KEY_ID',
}.items()}
LOGGING = {'version': 1, 'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'root': {'handlers': ['console'], 'level': 'INFO'}}

if os.getenv('REDIS_URL'):
    CACHES = {'default': {'BACKEND': 'django.core.cache.backends.redis.RedisCache',
                          'LOCATION': os.environ['REDIS_URL'], 'KEY_PREFIX': 'paidquiz'}}
DATA_UPLOAD_MAX_MEMORY_SIZE = 131072
