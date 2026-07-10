# ══════════════════════════════════════════════════════════════
# settings_prod.py — Sobreescrituras para PRODUCCIÓN
# Usar con: python manage.py runserver --settings=inversiones_ramon.settings_prod
# O definir:  DJANGO_SETTINGS_MODULE=inversiones_ramon.settings_prod
# ══════════════════════════════════════════════════════════════

from .settings import *          # hereda toda la config base
from decouple import config, Csv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


# ─────────────────────────────────────────────
# SEGURIDAD BÁSICA
# ─────────────────────────────────────────────
SECRET_KEY = config('SECRET_KEY')            # obligatorio en .env — sin default
DEBUG      = False
ALLOWED_HOSTS = config('ALLOWED_HOSTS', cast=Csv())


# ─────────────────────────────────────────────
# MIDDLEWARE — WhiteNoise para archivos estáticos
# ─────────────────────────────────────────────
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',   # ← justo después de Security
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'


# ─────────────────────────────────────────────
# BASE DE DATOS — PostgreSQL
# ─────────────────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE':       'django.db.backends.postgresql',
        'NAME':         config('DB_NAME',     default='inversiones_ramon_db'),
        'USER':         config('DB_USER',     default='postgres'),
        'PASSWORD':     config('DB_PASSWORD'),
        'HOST':         config('DB_HOST',     default='localhost'),
        'PORT':         config('DB_PORT',     default='5432'),
        'CONN_MAX_AGE': config('DB_CONN_MAX_AGE', default=60, cast=int),
        # Sin connect_timeout la petición cuelga indefinidamente si la BD
        # es inalcanzable. 10 segundos es suficiente para distinguir un
        # problema de red de una BD simplemente lenta.
        'OPTIONS': {'connect_timeout': 10},
    }
}


# ─────────────────────────────────────────────
# CORREO — SMTP real
# ─────────────────────────────────────────────
EMAIL_BACKEND       = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST          = config('EMAIL_HOST',     default='smtp.gmail.com')
EMAIL_PORT          = config('EMAIL_PORT',     default=587,   cast=int)
EMAIL_USE_TLS       = config('EMAIL_USE_TLS',  default=True,  cast=bool)
EMAIL_HOST_USER     = config('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL  = config('DEFAULT_FROM_EMAIL',
                             default='Inversiones Ramón <noreply@inversionesramon.com>')


# ─────────────────────────────────────────────
# CABECERAS DE SEGURIDAD HTTPS
# ─────────────────────────────────────────────
SECURE_SSL_REDIRECT              = True
SESSION_COOKIE_SECURE            = True
CSRF_COOKIE_SECURE               = True
SECURE_BROWSER_XSS_FILTER        = True
SECURE_CONTENT_TYPE_NOSNIFF      = True
X_FRAME_OPTIONS                  = 'DENY'
SECURE_HSTS_SECONDS              = 31536000   # 1 año
SECURE_HSTS_INCLUDE_SUBDOMAINS   = True
SECURE_HSTS_PRELOAD              = True

# ── Detección de HTTPS detrás de un proxy inverso (Nginx/Apache) ──
# gunicorn no maneja TLS por sí mismo: el certificado se termina en
# Nginx, que reenvía la petición a gunicorn por HTTP plano. Sin esta
# configuración, Django ve TODAS las peticiones como HTTP y,
# combinado con SECURE_SSL_REDIRECT=True arriba, provoca un LOOP
# INFINITO de redirecciones (Django redirige a HTTPS → Nginx reenvía
# por HTTP → Django redirige de nuevo...).
#
# ⚠️ REQUISITO INDISPENSABLE en la configuración de Nginx, para que
# el cliente no pueda falsificar este encabezado:
#
#     location / {
#         proxy_set_header X-Forwarded-Proto $scheme;
#         proxy_pass http://127.0.0.1:8000;
#     }
#
# Si gunicorn recibe tráfico DIRECTO de internet (sin Nginx/Apache
# delante) — caso muy poco común — desactivar esto en .env con
# BEHIND_PROXY=False, o el sitio quedará inaccesible.
if config('BEHIND_PROXY', default=True, cast=bool):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')


# ─────────────────────────────────────────────
# CSRF — orígenes de confianza
# ─────────────────────────────────────────────
# Necesario en Django 4+ para que los formularios POST funcionen
# cuando el sitio se sirve por HTTPS bajo el/los dominios reales.
# Formato: lista separada por comas, CON esquema (https://).
# Ejemplo en .env:
#   CSRF_TRUSTED_ORIGINS=https://inversionesramon.com,https://www.inversionesramon.com
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default='', cast=Csv())


# ─────────────────────────────────────────────
# SESIONES — cookies seguras
# ─────────────────────────────────────────────
SESSION_COOKIE_HTTPONLY          = True
CSRF_COOKIE_HTTPONLY             = True


# ─────────────────────────────────────────────
# LOGGING — archivo rotativo en producción
# ─────────────────────────────────────────────
LOG_DIR = BASE_DIR / 'logs'

try:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    _logs_disponibles = True
except OSError:
    # Si el proceso no tiene permisos de escritura sobre BASE_DIR
    # (común en despliegues donde la app corre con un usuario sin
    # privilegios), NO debe impedir que Django arranque. Se cae a
    # registrar solo en consola, que gunicorn/systemd capturan en
    # su propio log de servicio.
    _logs_disponibles = False

_handlers_archivo = {
    'file_errors': {
        'class':       'logging.handlers.RotatingFileHandler',
        'filename':    LOG_DIR / 'errores.log',
        'maxBytes':    5 * 1024 * 1024,   # 5 MB
        'backupCount': 5,
        'formatter':   'prod',
    },
    'file_django': {
        'class':       'logging.handlers.RotatingFileHandler',
        'filename':    LOG_DIR / 'django.log',
        'maxBytes':    5 * 1024 * 1024,
        'backupCount': 3,
        'formatter':   'prod',
    },
} if _logs_disponibles else {}

_handler_errores  = 'file_errors' if _logs_disponibles else 'console_prod'
_handler_django   = 'file_django' if _logs_disponibles else 'console_prod'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'prod': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        **_handlers_archivo,
        'console_prod': {
            'class':     'logging.StreamHandler',
            'formatter': 'prod',
        },
    },
    'root': {
        'handlers': [_handler_errores],
        'level':    'ERROR',
    },
    'loggers': {
        'django': {
            'handlers':  [_handler_django],
            'level':     'WARNING',
            'propagate': False,
        },
        'django.request': {
            'handlers':  [_handler_errores],
            'level':     'ERROR',
            'propagate': False,
        },
    },
}
