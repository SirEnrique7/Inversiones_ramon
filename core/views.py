from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
from django.db.models import F, Q, Sum, Count
import json
from datetime import date, timedelta

from .models import Usuario, TasaCambio, AuditoriaAccion
from .forms import (
    LoginForm, UsuarioCrearForm, UsuarioEditarForm,
    RecuperarPasswordForm, NuevaPasswordForm
)
from .decorators_core import login_requerido, solo_admin
from .bcv_scraper import actualizar_tasa_hoy

import threading # CORRECCIÓN: Para evitar el bloqueo de hilos en el login


# ─────────────────────────────────────────────
# AUTH: Login / Logout
# ─────────────────────────────────────────────

def vista_login(request):
    if request.user.is_authenticated:
        return redirect('core:dashboard')

    form = LoginForm(request, data=request.POST or None)

    if request.method == 'POST':
        if form.is_valid():
            usuario = form.get_user()
            login(request, usuario)

            AuditoriaAccion.registrar(
                usuario=usuario, accion='login',
                descripcion='Inicio de sesión exitoso.',
                request=request,
            )

            # CORRECCIÓN: Se ejecuta el scraper en un hilo secundario (Thread) 
            # para que el login responda de inmediato sin esperar la respuesta de la web del BCV
            try:
                threading.Thread(target=actualizar_tasa_hoy, daemon=True).start()
            except Exception:
                pass 

            return redirect('core:dashboard')
        else:
            username_intent = request.POST.get('username', '')
            AuditoriaAccion.registrar(
                usuario=None, accion='login_fallido',
                descripcion=f'Intento fallido para usuario: "{username_intent}"',
                request=request,
            )
            messages.error(request, 'Usuario o contraseña incorrectos.')

    return render(request, 'core/login.html', {'form': form})


@login_requerido
def vista_logout(request):
    AuditoriaAccion.registrar(
        usuario=request.user, accion='logout',
        descripcion='Cierre de sesión.',
        request=request,
    )
    logout(request)
    return redirect('core:login')


# ─────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────

@login_requerido
def dashboard(request):
    from inventario.models import Producto
    from compras.models import Compra
    from ventas.models import Venta

    tasa_hoy    = TasaCambio.tasa_vigente()
    hoy         = date.today()

    total_productos    = Producto.objects.filter(activo=True).count()
    productos_bajo     = Producto.objects.filter(
        activo=True, stock_actual__lte=F('stock_minimo')
    ).order_by('stock_actual')[:5]
    compras_pendientes = Compra.objects.filter(estado='pendiente').count()
    ventas_mes         = Venta.objects.filter(
        fecha__year=hoy.year, fecha__month=hoy.month,
        estado__in=['procesada', 'a_credito', 'pagada']
    ).count()

    context = {
        'tasa_hoy':             tasa_hoy,
        'total_productos':      total_productos,
        'productos_bajo':       productos_bajo,
        'compras_pendientes':   compras_pendientes,
        'ventas_mes':           ventas_mes,
        'puede_ver_financiero': request.user.es_admin(),
    }

    if request.user.es_admin():
        from core.models_bimonetario import CuentaPorCobrar, CuentaPorPagar

        context['cuentas_por_cobrar'] = CuentaPorCobrar.objects.filter(
            estado='pendiente'
        ).aggregate(t=Sum('saldo_restante'))['t'] or 0

        context['cuentas_por_pagar'] = CuentaPorPagar.objects.filter(
            estado='pendiente'
        ).aggregate(t=Sum('saldo_restante'))['t'] or 0

        context['creditos_vencidos'] = CuentaPorCobrar.objects.filter(
            estado='pendiente', fecha_estimada_pago__lt=hoy
        ).count()

        context['ventas_hoy'] = Venta.objects.filter(
            fecha=hoy, estado__in=['procesada', 'a_credito', 'pagada']
        ).aggregate(t=Sum('total_bs'))['t'] or 0

        # ── Chart 1: ventas últimos 7 días — una sola query ──
        from django.db.models.functions import TruncDate
        hace_6 = hoy - timedelta(days=6)
        ventas_rango = (
            Venta.objects.filter(
                fecha__gte=hace_6,
                fecha__lte=hoy,
                estado__in=['procesada', 'a_credito', 'pagada']
            )
            .annotate(dia=TruncDate('fecha'))
            .values('dia')
            .annotate(t=Sum('total_bs'))
            .order_by('dia')
        )
        ventas_por_dia = {row['dia']: row['t'] for row in ventas_rango}

        labels_7d, ventas_7d = [], []
        for i in range(6, -1, -1):
            dia   = hoy - timedelta(days=i)
            total = ventas_por_dia.get(dia) or 0
            labels_7d.append(dia.strftime('%d/%m'))
            ventas_7d.append(round(float(total), 2))

        # ── Chart 2: compras por estado ──
        compras_estados = dict(
            Compra.objects.values_list('estado').annotate(c=Count('id'))
        )
        estado_labels  = ['Pendiente', 'Aprobada', 'Recibida', 'Rechazada', 'Cancelada']
        estado_keys    = ['pendiente', 'aprobada', 'recibida', 'rechazada', 'cancelada']
        estado_valores = [compras_estados.get(k, 0) for k in estado_keys]

        # ── Chart 3: top 5 productos stock crítico ──
        criticos = list(
            Producto.objects.filter(activo=True, stock_actual__lte=F('stock_minimo'))
            .order_by('stock_actual')
            .values('nombre', 'stock_actual', 'stock_minimo')[:5]
        )

        # ── Actividad reciente ──
        actividad = AuditoriaAccion.objects.select_related('usuario').order_by('-id')[:6]

        context.update({
            'chart_labels_7d':      json.dumps(labels_7d),
            'chart_ventas_7d':      json.dumps(ventas_7d),
            'chart_estado_labels':  json.dumps(estado_labels),
            'chart_estado_valores': json.dumps(estado_valores),
            'chart_criticos_nombres': json.dumps([c['nombre'][:18] for c in criticos]),
            'chart_criticos_stock':   json.dumps([c['stock_actual'] for c in criticos]),
            'chart_criticos_minimo':  json.dumps([c['stock_minimo'] for c in criticos]),
            'actividad_reciente':   actividad,
        })

    return render(request, 'core/dashboard.html', context)


# ─────────────────────────────────────────────
# GESTIÓN DE USUARIOS (solo Admin)
# ─────────────────────────────────────────────

@solo_admin
def lista_usuarios(request):
    from django.core.paginator import Paginator
    qs = Usuario.objects.all().order_by('-is_active', 'last_name', 'first_name')

    params = request.GET.copy()
    params.pop('page', None)
    filter_params = params.urlencode()

    paginator = Paginator(qs, 20)
    page_obj  = paginator.get_page(request.GET.get('page'))

    return render(request, 'core/lista_usuarios.html', {
        'usuarios':      page_obj,
        'page_obj':      page_obj,
        'filter_params': filter_params,
    })


@solo_admin
def crear_usuario(request):
    if request.method == 'POST':
        form = UsuarioCrearForm(request.POST)
        if form.is_valid():
            usuario = form.save()
            AuditoriaAccion.registrar(
                usuario=request.user, accion='alta_usuario',
                descripcion=f'Usuario creado: {usuario.get_nombre_completo()} ({usuario.cedula})',
                request=request, objeto_tipo='Usuario', objeto_id=usuario.pk,
            )
            messages.success(request, f'Usuario "{usuario.get_nombre_completo()}" creado correctamente.')
            return redirect('core:lista_usuarios')
    else:
        form = UsuarioCrearForm()

    return render(request, 'core/form_usuario.html', {
        'form':   form,
        'titulo': 'Nuevo usuario',
        'accion': 'Crear',
    })


@solo_admin
def editar_usuario(request, pk):
    usuario = get_object_or_404(Usuario, pk=pk)

    if request.method == 'POST':
        form = UsuarioEditarForm(request.POST, instance=usuario)
        if form.is_valid():
            form.save()
            AuditoriaAccion.registrar(
                usuario=request.user, accion='edicion_usuario',
                descripcion=f'Usuario editado: {usuario.get_nombre_completo()}',
                request=request, objeto_tipo='Usuario', objeto_id=usuario.pk,
            )
            messages.success(request, 'Usuario actualizado correctamente.')
            return redirect('core:lista_usuarios')
    else:
        form = UsuarioEditarForm(instance=usuario)

    return render(request, 'core/form_usuario.html', {
        'form':    form,
        'titulo':  f'Editar: {usuario.get_nombre_completo()}',
        'accion':  'Guardar cambios',
        'usuario': usuario,
    })


@solo_admin
def dar_de_baja(request, pk):
    usuario = get_object_or_404(Usuario, pk=pk)

    if usuario == request.user:
        messages.error(request, 'No puedes darte de baja a ti mismo.')
        return redirect('core:lista_usuarios')

    if request.method == 'POST':
        usuario.dar_de_baja(ejecutado_por=request.user)
        AuditoriaAccion.registrar(
            usuario=request.user, accion='baja_usuario',
            descripcion=f'Baja lógica ejecutada sobre: {usuario.get_nombre_completo()} ({usuario.cedula})',
            request=request, objeto_tipo='Usuario', objeto_id=usuario.pk,
        )
        messages.warning(request, f'Usuario "{usuario.get_nombre_completo()}" dado de baja.')
        return redirect('core:lista_usuarios')

    return render(request, 'core/confirmar_baja.html', {'usuario': usuario})


@solo_admin
def reactivar_usuario(request, pk):
    usuario = get_object_or_404(Usuario, pk=pk, is_active=False)
    if request.method == 'POST':
        usuario.reactivar(ejecutado_por=request.user)
        AuditoriaAccion.registrar(
            usuario=request.user, accion='reactivacion_usuario',
            descripcion=f'Reactivación de usuario: {usuario.get_nombre_completo()} ({usuario.cedula})',
            request=request, objeto_tipo='Usuario', objeto_id=usuario.pk,
        )
        messages.success(request, f'Usuario "{usuario.get_nombre_completo()}" reactivado.')
        return redirect('core:lista_usuarios')
    return render(request, 'core/confirmar_reactivar.html', {'usuario': usuario})


# ─────────────────────────────────────────────
# RECUPERACIÓN DE CONTRASEÑA
# ─────────────────────────────────────────────

def recuperar_password(request):
    if request.method == 'POST':
        form = RecuperarPasswordForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']

            # Siempre mostramos el mismo mensaje para no revelar si el correo
            # existe o no en la base de datos (evita enumeración de usuarios).
            try:
                usuario = Usuario.objects.get(email=email, is_active=True)
                uid     = urlsafe_base64_encode(force_bytes(usuario.pk))
                token   = default_token_generator.make_token(usuario)

                path_dinamico = reverse('core:reset_password', kwargs={'uidb64': uid, 'token': token})
                enlace = request.build_absolute_uri(path_dinamico)

                send_mail(
                    subject='Recuperación de contraseña — Inversiones Ramón',
                    message=(
                        f'Hola {usuario.get_nombre_completo()},\n\n'
                        f'Haz clic en el siguiente enlace para restablecer tu contraseña '
                        f'(válido por 15 minutos):\n\n{enlace}\n\n'
                        f'Si no solicitaste esto, ignora este mensaje.'
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    fail_silently=True,  # No exponemos errores SMTP al usuario
                )
            except Usuario.DoesNotExist:
                pass  # Silencioso: no revelar si el correo existe

            messages.success(request, 'Si el correo está registrado, recibirás un enlace de recuperación en breve.')
            return redirect('core:login')
    else:
        form = RecuperarPasswordForm()

    return render(request, 'core/recuperar_password.html', {'form': form})


def reset_password(request, uidb64, token):
    try:
        uid     = force_str(urlsafe_base64_decode(uidb64))
        usuario = Usuario.objects.get(pk=uid)
    except (TypeError, ValueError, Usuario.DoesNotExist):
        usuario = None

    if usuario is None or not default_token_generator.check_token(usuario, token):
        messages.error(request, 'El enlace es inválido o ha expirado.')
        return redirect('core:recuperar_password')

    if request.method == 'POST':
        form = NuevaPasswordForm(usuario, request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Contraseña actualizada correctamente. Inicia sesión.')
            return redirect('core:login')
    else:
        form = NuevaPasswordForm(usuario)

    return render(request, 'core/reset_password.html', {'form': form})


# ─────────────────────────────────────────────
# AUDITORÍA (solo Admin)
# ─────────────────────────────────────────────

@solo_admin
def log_auditoria(request):
    from django.core.paginator import Paginator
    qs = AuditoriaAccion.objects.select_related('usuario').all().order_by('-id')

    params = request.GET.copy()
    params.pop('page', None)
    filter_params = params.urlencode()

    paginator = Paginator(qs, 50)
    page_obj  = paginator.get_page(request.GET.get('page'))

    return render(request, 'core/auditoria.html', {
        'logs':          page_obj,
        'page_obj':      page_obj,
        'filter_params': filter_params,
    })


# ─────────────────────────────────────────────
# TASA BCV (solo Admin)
# ─────────────────────────────────────────────

@solo_admin
def historial_tasa(request):
    tasas = TasaCambio.objects.all().order_by('-fecha')[:30]
    return render(request, 'core/historial_tasa.html', {'tasas': tasas})


# ─────────────────────────────────────────────
# PÁGINAS DE ERROR PERSONALIZADAS
# ─────────────────────────────────────────────

def error_404(request, exception=None):
    return render(request, 'core/404.html', status=404)


def error_500(request):
    return render(request, 'core/500.html', status=500)