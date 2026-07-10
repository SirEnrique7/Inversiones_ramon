# ══════════════════════════════════════════════════════════════
# Selección automática de módulo de settings.
#
# Usado por manage.py, wsgi.py y asgi.py ANTES de que Django arranque,
# por eso es un módulo independiente sin importar nada de Django.
#
# Reglas:
#   1. Si DJANGO_SETTINGS_MODULE ya está definida como variable de
#      entorno del proceso (uso explícito/avanzado), se respeta tal cual
#      y no se hace nada más.
#   2. En caso contrario, se lee DJANGO_ENV (variable de entorno o
#      del archivo .env, vía python-decouple):
#        - DJANGO_ENV=production  -> inversiones_ramon.settings_prod
#        - cualquier otro valor / ausente -> inversiones_ramon.settings
#
# Esto permite activar TODA la configuración de producción
# (settings_prod.py: HTTPS forzado, cookies seguras, CSRF_TRUSTED_ORIGINS,
# logging a archivo, etc.) con una sola línea en .env:
#
#       DJANGO_ENV=production
#
# sin depender de configurar por separado DJANGO_SETTINGS_MODULE en el
# servicio systemd — un paso que es fácil olvidar y que, si se olvida,
# deja la aplicación corriendo con la configuración de DESARROLLO en
# producción sin ningún aviso.
# ══════════════════════════════════════════════════════════════

import os

_PROD = 'inversiones_ramon.settings_prod'
_DEV  = 'inversiones_ramon.settings'


def resolver_settings_module():
    # 1. Override explícito: si alguien ya fijó DJANGO_SETTINGS_MODULE
    #    en el entorno (por ejemplo, para pruebas con --settings o un
    #    despliegue que prefiere configurarlo así), se respeta.
    explicito = os.environ.get('DJANGO_SETTINGS_MODULE')
    if explicito:
        return explicito

    # 2. Si no, decide según DJANGO_ENV (entorno o .env).
    try:
        from decouple import config
        entorno = config('DJANGO_ENV', default='development')
    except Exception:
        # python-decouple no disponible o .env ilegible: ante la duda,
        # usar desarrollo (la opción más segura para no exponer un
        # despliegue a medio configurar como si fuera producción).
        entorno = 'development'

    if str(entorno).strip().lower() == 'production':
        return _PROD
    return _DEV
