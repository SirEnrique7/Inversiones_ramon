# ══════════════════════════════════════════════════════════════
# core/checks.py
#
# Chequeos de sistema de Django (django.core.checks) que se ejecutan
# automáticamente con:
#   - python manage.py check
#   - python manage.py check --deploy
#   - python manage.py migrate / runserver / etc. (Django los corre
#     antes de cualquier comando de gestión)
#
# Objetivo: convertir configuraciones "silenciosas" (que no rompen el
# arranque pero sí romperán funcionalidad real cuando un usuario real
# la use) en advertencias VISIBLES en el momento del despliegue, no
# tres semanas después cuando un cliente reporte "el formulario no
# funciona" sin más contexto.
# ══════════════════════════════════════════════════════════════

from django.conf import settings
from django.core.checks import Warning, Error, register, Tags


@register(Tags.security, deploy=True)
def check_csrf_trusted_origins_en_produccion(app_configs, **kwargs):
    """
    Si el sitio corre en producción (DEBUG=False) detrás de HTTPS y
    CSRF_TRUSTED_ORIGINS está vacío, todo formulario POST devolverá
    403 Forbidden en cuanto se acceda por el dominio real — un fallo
    que no aparece en pruebas locales por HTTP/localhost y que suele
    descubrirse solo cuando el sistema ya está en producción.
    """
    errores = []
    if not settings.DEBUG and not getattr(settings, 'CSRF_TRUSTED_ORIGINS', []):
        errores.append(
            Warning(
                'CSRF_TRUSTED_ORIGINS está vacío en un entorno de producción '
                '(DEBUG=False). Todos los formularios (login, ventas, compras, '
                'etc.) devolverán "403 Forbidden" al enviarse desde el dominio '
                'real servido por HTTPS.',
                hint=(
                    'Define CSRF_TRUSTED_ORIGINS en tu archivo .env, ej.: '
                    'CSRF_TRUSTED_ORIGINS=https://tu-dominio.com,'
                    'https://www.tu-dominio.com'
                ),
                id='core.W001',
            )
        )
    return errores


@register(Tags.security, deploy=True)
def check_email_configurado_en_produccion(app_configs, **kwargs):
    """
    Si el backend de correo es el SMTP real (producción) pero faltan
    credenciales, la recuperación de contraseña fallará en silencio
    para todos los usuarios (el error queda solo en logs/errores.log,
    ver core/views.py::recuperar_password). Esto lo detecta ANTES de
    que el primer usuario se queje de no recibir el correo.
    """
    errores = []
    backend = getattr(settings, 'EMAIL_BACKEND', '')
    if 'smtp' in backend.lower():
        faltantes = []
        if not getattr(settings, 'EMAIL_HOST_USER', ''):
            faltantes.append('EMAIL_HOST_USER')
        if not getattr(settings, 'EMAIL_HOST_PASSWORD', ''):
            faltantes.append('EMAIL_HOST_PASSWORD')
        if faltantes:
            errores.append(
                Warning(
                    f'Backend de correo SMTP configurado pero faltan: '
                    f'{", ".join(faltantes)}. La recuperación de contraseña '
                    f'no podrá enviar correos.',
                    hint='Completa estas variables en tu archivo .env.',
                    id='core.W002',
                )
            )
    return errores


@register(Tags.security, deploy=True)
def check_secret_key_por_defecto(app_configs, **kwargs):
    """
    Si el sistema arranca en producción con la SECRET_KEY de ejemplo
    que trae settings.py para desarrollo local, cualquiera con acceso
    al código fuente (o a este mismo repositorio) puede falsificar
    sesiones y tokens de recuperación de contraseña.
    """
    errores = []
    if not settings.DEBUG and 'django-insecure' in getattr(settings, 'SECRET_KEY', ''):
        errores.append(
            Error(
                'SECRET_KEY sigue siendo la clave de desarrollo por defecto '
                'en un entorno de producción (DEBUG=False). Esto compromete '
                'la seguridad de las sesiones y de los enlaces de '
                'recuperación de contraseña.',
                hint=(
                    'Genera una clave única y defínela en tu .env: '
                    'python3 -c "from django.core.management.utils import '
                    'get_random_secret_key; print(get_random_secret_key())"'
                ),
                id='core.E001',
            )
        )
    return errores
