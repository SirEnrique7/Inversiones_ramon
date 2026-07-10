# ══════════════════════════════════════════════════════════════
# CONTEXT PROCESSOR — Inyecta tasa BCV en todos los templates
# Registrar en TEMPLATES > OPTIONS > context_processors
# ══════════════════════════════════════════════════════════════

from .models import TasaCambio


def tasa_bcv(request):
    """Disponible como {{ tasa_bcv }} en cualquier template.

    IMPORTANTE: este context processor se ejecuta en CADA render de
    plantilla, incluyendo la página de error 500. Si la base de datos
    no está disponible (caída temporal, límite de conexiones, etc.),
    NINGUNA consulta —incluida `request.user.is_authenticated`, que
    también golpea la BD para resolver la sesión— puede dejar escapar
    una excepción aquí, o la página de error personalizada (500.html)
    fallaría también al intentar renderizarse, dejando al usuario sin
    ninguna respuesta útil.

    Por eso TODO el cuerpo está protegido: cualquier error (de BD o de
    otro tipo) simplemente desactiva la tasa para esa petición.
    """
    try:
        if request.user.is_authenticated:
            return {'tasa_bcv': TasaCambio.tasa_vigente()}
    except Exception:
        pass

    return {'tasa_bcv': None}