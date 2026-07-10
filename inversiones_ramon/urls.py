# ══════════════════════════════════════════════════════════════
# urls.py — Archivo principal del proyecto
# Ubicación: inversiones_ramon/urls.py
# ══════════════════════════════════════════════════════════════

from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

urlpatterns = [
    path('django-admin/', admin.site.urls),
    path('', include('core.urls_core', namespace='core')),
    path('inventario/', include('inventario.urls', namespace='inventario')),
    path('compras/', include('compras.urls', namespace='compras')),
    path('ventas/', include('ventas.urls', namespace='ventas')),
    path('reportes/', include('reportes.urls', namespace='reportes')),
]

# ── Páginas de error personalizadas ──
handler404 = 'core.views.error_404'
handler500 = 'core.views.error_500'
