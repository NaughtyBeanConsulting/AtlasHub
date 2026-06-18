"""
Django settings for AtlasHub.

All deployment-specific values come from the repo-root .env file
(loaded with python-dotenv). Never hardcode secrets here.
"""
from pathlib import Path
import os

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')


def env_bool(name, default='False'):
    return os.environ.get(name, default).strip().lower() in ('1', 'true', 'yes', 'on')


SECRET_KEY = os.environ['SECRET_KEY']
DEBUG = env_bool('DEBUG')
ALLOWED_HOSTS = [h.strip() for h in os.environ.get('ALLOWED_HOSTS', '').split(',') if h.strip()]

# Absolute base URL of this deployment — used to build links sent over
# WhatsApp/email (password resets, notifications).
SITE_URL = os.environ.get('SITE_URL', 'http://127.0.0.1:8000').rstrip('/')

# ── Security hardening ───────────────────────────────────────────────────────
# Everything here engages automatically once DEBUG is off; the HTTPS-only
# pieces additionally require SITE_URL to be an https:// URL (TLS terminating
# in front of Django). Behind a reverse proxy we trust X-Forwarded-Proto.
_HTTPS = SITE_URL.startswith('https://')
if _HTTPS:
    CSRF_TRUSTED_ORIGINS = [SITE_URL]
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

if not DEBUG:
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = 'same-origin'
    X_FRAME_OPTIONS = 'DENY'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    CSRF_COOKIE_SAMESITE = 'Lax'
    if _HTTPS:
        SECURE_SSL_REDIRECT = env_bool('SECURE_SSL_REDIRECT', 'True')
        SESSION_COOKIE_SECURE = True
        CSRF_COOKIE_SECURE = True
        SECURE_HSTS_SECONDS = int(os.environ.get('SECURE_HSTS_SECONDS', '31536000'))
        SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool('SECURE_HSTS_INCLUDE_SUBDOMAINS', 'True')
        SECURE_HSTS_PRELOAD = env_bool('SECURE_HSTS_PRELOAD', 'True')

# ── Apps ─────────────────────────────────────────────────────────────────────

INSTALLED_APPS = [
    # unfold must precede django.contrib.admin
    'unfold',
    'unfold.contrib.filters',
    'unfold.contrib.forms',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'accounts',
    'core',
    'projects',
    'wiki',
    'whatsapp',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'app.urls'

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
                'core.context_processors.nav_spaces',
            ],
        },
    },
]

WSGI_APPLICATION = 'app.wsgi.application'

# ── Database ─────────────────────────────────────────────────────────────────

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME'),
        'USER': os.environ.get('DB_USER'),
        'PASSWORD': os.environ.get('DB_PASSWORD'),
        'HOST': os.environ.get('DB_HOST', '127.0.0.1'),
        'PORT': os.environ.get('DB_PORT', '5432'),
        # Reuse connections across requests (0 = close every request, dev default).
        'CONN_MAX_AGE': int(os.environ.get('DB_CONN_MAX_AGE', '0' if DEBUG else '60')),
        'CONN_HEALTH_CHECKS': True,
    }
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── Auth ─────────────────────────────────────────────────────────────────────

AUTH_USER_MODEL = 'accounts.User'
LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'accounts:login'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ── I18N / TZ ────────────────────────────────────────────────────────────────

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Johannesburg'
USE_I18N = True
USE_TZ = True

# ── Static files ─────────────────────────────────────────────────────────────

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {
        'BACKEND': (
            'django.contrib.staticfiles.storage.StaticFilesStorage'
            if DEBUG else
            'whitenoise.storage.CompressedManifestStaticFilesStorage'
        )
    },
}

# ── Email (password-reset fallback channel) ──────────────────────────────────

if os.environ.get('EMAIL_HOST'):
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = os.environ['EMAIL_HOST']
    EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
    EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
    EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
    EMAIL_USE_TLS = env_bool('EMAIL_USE_TLS', 'True')
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'AtlasHub <noreply@atlashub.local>')

# ── Phone / WhatsApp ─────────────────────────────────────────────────────────

# Default dialling code for normalising local numbers to E.164 (27 = South Africa).
PHONE_DEFAULT_DIAL_CODE = os.environ.get('COUNTRY_CODE', '27')

# AtlasHub shares ClockInSop's WhatsApp worker, so it must NOT manage the session
# (no QR pairing / restart / disconnect — those would affect every app sharing
# the one number). Only the worker's owner sets this True.
WHATSAPP_MANAGES_SESSION = env_bool('WHATSAPP_MANAGES_SESSION', 'False')

# ── Admin (django-unfold) ────────────────────────────────────────────────────

UNFOLD = {
    'SITE_TITLE': 'AtlasHub admin',
    'SITE_HEADER': 'AtlasHub',
    'SITE_SUBHEADER': 'Back office',
    'SITE_URL': '/',
}

# ── Logging ──────────────────────────────────────────────────────────────────
# Single console handler so gunicorn/systemd capture everything in the journal.
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'DEBUG' if DEBUG else 'INFO').upper()
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '[{asctime}] {levelname} {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'standard'},
    },
    'root': {'handlers': ['console'], 'level': LOG_LEVEL},
    'loggers': {
        'django': {'handlers': ['console'], 'level': LOG_LEVEL, 'propagate': False},
        # Surface CSRF/host-header/SSL warnings even when the root level is higher.
        'django.security': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
    },
}

# ── Error tracking (Sentry) ──────────────────────────────────────────────────
# Disabled unless SENTRY_DSN is set, so dev/CI stay silent by default. The Django
# integration is auto-enabled by sentry-sdk. send_default_pii attaches request
# headers and the logged-in user to events — keep it on only where that's allowed.
SENTRY_DSN = os.environ.get('SENTRY_DSN', '').strip()
if SENTRY_DSN:
    import sentry_sdk

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=os.environ.get('SENTRY_ENVIRONMENT', 'development' if DEBUG else 'production'),
        release=os.environ.get('SENTRY_RELEASE') or None,
        # Performance tracing: off by default; raise toward 1.0 to sample transactions.
        traces_sample_rate=float(os.environ.get('SENTRY_TRACES_SAMPLE_RATE', '0.0')),
        send_default_pii=env_bool('SENTRY_SEND_DEFAULT_PII', 'True'),
    )
