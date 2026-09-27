from django.apps import AppConfig
class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'Core — Autenticación y Control'

    def ready(self):
        # Registra los chequeos de sistema personalizados (ver core/checks.py).
        # Se importan aquí, no al nivel del módulo, porque Django exige que
        # las apps ya estén cargadas antes de que los checks puedan usar
        # cualquier cosa dependiente del registro de apps.
        from . import checks  # noqa: F401
