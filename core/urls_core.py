from django.urls import path
from django.shortcuts import redirect
from . import views as views_core
from . import views_bimonetario as vbm

app_name = 'core'


def root_redirect(request):
    """Raíz: si hay sesión va al dashboard, si no al login."""
    if request.user.is_authenticated:
        return redirect('core:dashboard')
    return redirect('core:login')


urlpatterns = [

    # ── Raíz inteligente ──
    path('', root_redirect, name='home'),

    # ── Auth ──
    path('login/',   views_core.vista_login,  name='login'),
    path('logout/',  views_core.vista_logout, name='logout'),

    # ── Dashboard (URL propia para evitar colisión con raíz) ──
    path('inicio/', views_core.dashboard, name='dashboard'),

    # ── Usuarios ──
    path('usuarios/',                    views_core.lista_usuarios,    name='lista_usuarios'),
    path('usuarios/nuevo/',              views_core.crear_usuario,     name='crear_usuario'),
    path('usuarios/<int:pk>/editar/',    views_core.editar_usuario,    name='editar_usuario'),
    path('usuarios/<int:pk>/baja/',      views_core.dar_de_baja,       name='dar_de_baja'),
    path('usuarios/<int:pk>/reactivar/', views_core.reactivar_usuario, name='reactivar_usuario'),

    # ── Recuperación de contraseña ──
    path('auth/recuperar/',              views_core.recuperar_password, name='recuperar_password'),
    path('auth/reset/<uidb64>/<token>/', views_core.reset_password,    name='reset_password'),

    # ── Auditoría y tasa ──
    path('auditoria/',  views_core.log_auditoria,  name='auditoria'),
    path('tasa-bcv/',   views_core.historial_tasa, name='historial_tasa'),

    # ── Cuentas por Pagar ──
    path('cuentas-pagar/',                   vbm.lista_cuentas_pagar,       name='lista_cuentas_pagar'),
    path('cuentas-pagar/<int:pk>/',          vbm.detalle_cuenta_pagar,      name='detalle_cuenta_pagar'),
    path('cuentas-pagar/<int:pk>/abono/',    vbm.registrar_abono_proveedor, name='registrar_abono_proveedor'),

    # ── Cuentas por Cobrar ──
    path('cuentas-cobrar/',                  vbm.lista_cuentas_cobrar,      name='lista_cuentas_cobrar'),
    path('cuentas-cobrar/<int:pk>/',         vbm.detalle_cuenta_cobrar,     name='detalle_cuenta_cobrar'),
    path('cuentas-cobrar/<int:pk>/pago/',    vbm.registrar_pago_cliente,    name='registrar_pago_cliente'),

    # ── Clientes ──
    path('clientes/',                vbm.lista_clientes,  name='lista_clientes'),
    path('clientes/nuevo/',          vbm.crear_cliente,   name='crear_cliente'),
    path('clientes/<int:pk>/editar/', vbm.editar_cliente, name='editar_cliente'),
]
