from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def solo_admin(view_func):
    """Vista accesible únicamente por usuarios con rol 'admin'."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('core:login')
        
        # Se usa getattr para evitar alertas de atributo desconocido en Pylance
        rol_usuario = getattr(request.user, 'rol', None)
        if rol_usuario != 'admin':
            messages.error(request, 'No tienes permiso para acceder a esta sección.')
            return redirect('core:dashboard')
            
        return view_func(request, *args, **kwargs)
    return wrapper


def solo_encargado(view_func):
    """Vista accesible únicamente por usuarios con rol 'encargado'."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('core:login')
        
        # Se usa getattr para evitar alertas de atributo desconocido en Pylance
        rol_usuario = getattr(request.user, 'rol', None)
        if rol_usuario != 'encargado':
            messages.error(request, 'Esta sección es solo para encargados.')
            return redirect('core:dashboard')
            
        return view_func(request, *args, **kwargs)
    return wrapper


def login_requerido(view_func):
    """Requiere que el usuario esté autenticado."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('core:login')
        return view_func(request, *args, **kwargs)
    return wrapper