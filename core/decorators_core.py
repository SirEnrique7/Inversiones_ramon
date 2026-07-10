# ══════════════════════════════════════════════════════════════
# DECORATORS — Control de acceso por rol (RBAC)
# Reemplaza decorators.py existente
# ══════════════════════════════════════════════════════════════

from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def login_requerido(view_func):
    """Requiere sesión activa. Redirige al login si no."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('core:login')
        return view_func(request, *args, **kwargs)
    return wrapper


def solo_admin(view_func):
    """
    Solo Administradores activos.
    Los encargados ven un mensaje de acceso denegado.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('core:login')
        if not request.user.es_admin():
            messages.error(request, 'Acceso restringido: se requiere rol Administrador.')
            return redirect('core:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def solo_encargado(view_func):
    """Solo Encargados/Almacenistas."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('core:login')
        if not request.user.es_encargado():
            messages.error(request, 'Esta sección es exclusiva para encargados.')
            return redirect('core:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def bloquear_encargado():
    """
    Inyecta de forma segura la variable 'puede_ver_financiero' en el objeto request.
    De este modo, estará disponible de forma idéntica en la vista y en el template
    como {{ puede_ver_financiero }} gracias al procesador de contexto de Django.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Inyectamos el flag en el request ANTES de procesar la vista
            if request.user.is_authenticated:
                request.puede_ver_financiero = request.user.es_admin()
            else:
                request.puede_ver_financiero = False
                
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator