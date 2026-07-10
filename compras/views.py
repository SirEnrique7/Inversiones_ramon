# ══════════════════════════════════════════════════════════════
# VIEWS — Módulo Compras (Versión Final Verificada y Certificada)
# ══════════════════════════════════════════════════════════════

import logging
logger = logging.getLogger(__name__)

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Sum
from django.forms import modelformset_factory
from decimal import Decimal
from typing import TYPE_CHECKING

from django.db.models import F as Fexpr
from .models import Compra, DetalleCompra
from .forms  import (
    CompraForm, DetalleCompraFormSet,
    AprobarCompraForm, RecepcionCompraForm,
    DetalleRecepcionForm, MarcarPagadoForm,
)
from core.models             import AuditoriaAccion, TasaCambio
from core.models_bimonetario import CuentaPorPagar
from core.decorators_core    import login_requerido, solo_admin
from inventario.models       import MovimientoInventario, Producto

# Declaración estática para que Pylance comprenda las relaciones inversas del ORM
if TYPE_CHECKING:
    from django.db.models.manager import RelatedManager
    class CompraConDetalles(Compra):
        detalles: RelatedManager[DetalleCompra]


# ─────────────────────────────────────────────
# LISTA DE COMPRAS
# ─────────────────────────────────────────────
@login_requerido
def lista_compras(request):
    import csv
    from django.http import HttpResponse
    from django.core.paginator import Paginator

    estado = request.GET.get('estado', '')
    q      = request.GET.get('q', '')

    qs = Compra.objects.select_related('proveedor', 'creada_por', 'aprobada_por')

    if not request.user.es_admin():
        qs = qs.filter(creada_por=request.user)

    if estado:
        qs = qs.filter(estado=estado)
    if q:
        qs = qs.filter(
            Q(numero_referencia__icontains=q) |
            Q(proveedor__nombre__icontains=q)
        )

    qs = qs.order_by('-fecha_creacion')

    # ── Exportar CSV ──
    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
        response['Content-Disposition'] = 'attachment; filename="compras.csv"'
        writer = csv.writer(response)
        writer.writerow([
            'N° Referencia', 'Fecha Creación', 'Proveedor', 'Estado',
            'Total Bs', 'Fecha Estimada', 'Creada por',
        ])
        for c in qs:
            writer.writerow([
                c.numero_referencia,
                c.fecha_creacion.strftime('%d/%m/%Y'),
                c.proveedor.nombre,
                c.get_estado_display(),
                c.total or '',
                c.fecha_estimada.strftime('%d/%m/%Y') if c.fecha_estimada else '',
                c.creada_por.get_nombre_completo() if c.creada_por else '',
            ])
        return response

    pendientes = Compra.objects.filter(estado='pendiente').count() if request.user.es_admin() else 0

    # ── Paginación ──
    params = request.GET.copy()
    params.pop('page', None)
    params.pop('export', None)
    filter_params = params.urlencode()

    paginator = Paginator(qs, 20)
    page_obj  = paginator.get_page(request.GET.get('page'))

    return render(request, 'compras/lista_compras.html', {
        'compras':       page_obj,
        'page_obj':      page_obj,
        'filter_params': filter_params,
        'estados':       Compra.ESTADO_CHOICES,
        'estado':        estado,
        'q':             q,
        'pendientes':    pendientes,
    })


# ─────────────────────────────────────────────
# CREAR ORDEN (Sincronizado con HTML Dinámico)
# ─────────────────────────────────────────────
@login_requerido
def crear_compra(request):
    from inventario.models import Producto
    sugerencias = []
    proveedor_id = request.GET.get('proveedor') or request.POST.get('proveedor')

    # En PostgreSQL un valor no numérico en un filtro de FK lanza ValueError
    # al evaluar el queryset. Validamos antes de tocar el ORM.
    if proveedor_id and not proveedor_id.isdigit():
        proveedor_id = None

    if proveedor_id:
        sugerencias = Producto.objects.filter(
            proveedor_id=proveedor_id, activo=True
        ).filter(
            Q(stock_actual__lte=Fexpr('stock_minimo')) | Q(en_tendencia=True)
        ).order_by('stock_actual')[:10]

    if request.method == 'POST':
        form    = CompraForm(request.POST)
        formset = DetalleCompraFormSet(request.POST, prefix='form')

        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    compra             = form.save(commit=False)
                    compra.creada_por  = request.user
                    compra.estado      = 'pendiente'
                    compra.save()

                    # Guardado controlado para forzar cálculos de subtotales por fila
                    detalles_instancias = formset.save(commit=False)
                    for detalle in detalles_instancias:
                        detalle.compra = compra
                        detalle.save()
                    
                    formset.save_m2m()

                    # Cálculo matemático global sobre los subtotales reales asentados
                    compra.calcular_total()

                AuditoriaAccion.registrar(
                    usuario=request.user, accion='crear_compra',
                    descripcion=f'Orden {compra.numero_referencia} creada — {compra.proveedor}',
                    request=request, objeto_tipo='Compra', objeto_id=compra.pk,
                )
                messages.success(
                    request,
                    f'Orden {compra.numero_referencia} creada y enviada al administrador para aprobación.'
                )
                return redirect('compras:detalle_compra', pk=compra.pk)
            except Exception:
                logger.exception('Error al crear orden de compra — usuario: %s', request.user)
                messages.error(request, 'Ocurrió un error al procesar la orden. Intenta de nuevo.')
        else:
            messages.error(request, 'Revisa los errores en el formulario de productos.')
    else:
        form    = CompraForm()
        formset = DetalleCompraFormSet(queryset=DetalleCompra.objects.none(), prefix='form')

    return render(request, 'compras/form_compra.html', {
        'form':        form,
        'formset':     formset,
        'titulo':      'Nueva orden de compra',
        'sugerencias': sugerencias,
    })


# ─────────────────────────────────────────────
# DETALLE DE COMPRA (Tipado Asistido)
# ─────────────────────────────────────────────
@login_requerido
def detalle_compra(request, pk):
    # El casteo mediante comentario le indica a VS Code la estructura extendida
    compra: 'CompraConDetalles' = get_object_or_404(Compra, pk=pk) # type: ignore

    if not request.user.es_admin() and compra.creada_por != request.user:
        messages.error(request, 'No tienes acceso a esta orden.')
        return redirect('compras:lista_compras')

    detalles = compra.detalles.select_related('producto').all()
    cuenta   = getattr(compra, 'cuenta_por_pagar', None)

    return render(request, 'compras/detalle_compra.html', {
        'compra':   compra,
        'detalles': detalles,
        'cuenta':   cuenta,
    })


# ─────────────────────────────────────────────
# APROBAR / RECHAZAR (Tipado Asistido)
# ─────────────────────────────────────────────
@solo_admin
def aprobar_compra(request, pk):
    compra: 'CompraConDetalles' = get_object_or_404(Compra, pk=pk, estado='pendiente') # type: ignore

    if request.method == 'POST':
        form = AprobarCompraForm(request.POST)
        if form.is_valid():
            decision = form.cleaned_data['decision']
            motivo   = form.cleaned_data['motivo_rechazo']

            with transaction.atomic():
                compra.estado            = decision
                compra.aprobada_por      = request.user
                compra.fecha_aprobacion  = timezone.now()
                if motivo:
                    compra.motivo_rechazo = motivo
                compra.save()

            accion = 'aprobar_compra' if decision == 'aprobada' else 'rechazar_compra'
            AuditoriaAccion.registrar(
                usuario=request.user, accion=accion,
                descripcion=f'Orden {compra.numero_referencia} {decision}. {motivo}',
                request=request, objeto_tipo='Compra', objeto_id=compra.pk,
            )

            if decision == 'aprobada':
                messages.success(
                    request,
                    f'Orden {compra.numero_referencia} aprobada. El encargado puede ver que está "En camino".'
                )
            else:
                messages.warning(request, f'Orden {compra.numero_referencia} rechazada.')

            return redirect('compras:detalle_compra', pk=compra.pk)
    else:
        form = AprobarCompraForm()

    return render(request, 'compras/aprobar_compra.html', {
        'compra':   compra,
        'detalles': compra.detalles.select_related('producto').all(),
        'form':     form,
    })


# ─────────────────────────────────────────────
# REGISTRAR RECEPCIÓN (Flujo Seguro Completo)
# ─────────────────────────────────────────────
@solo_admin
def recibir_compra(request, pk):
    compra: 'CompraConDetalles' = get_object_or_404(Compra, pk=pk, estado='aprobada') # type: ignore
    detalles = compra.detalles.select_related('producto').all()

    RecepcionFormSet = modelformset_factory(
        DetalleCompra,
        form=DetalleRecepcionForm,
        extra=0,
    )

    if request.method == 'POST':
        form_recepcion = RecepcionCompraForm(request.POST, instance=compra)
        formset        = RecepcionFormSet(request.POST, queryset=detalles)

        if form_recepcion.is_valid() and formset.is_valid():
            with transaction.atomic():
                # Lock de la compra para evitar doble recepción simultánea
                compra_locked = (
                    Compra.objects
                    .select_for_update()
                    .get(pk=compra.pk)
                )
                if compra_locked.estado != 'aprobada':
                    messages.error(request, 'Esta orden ya fue procesada por otra sesión.')
                    return redirect('compras:detalle_compra', pk=compra.pk)

                # Desconectamos temporalmente la señal que recalcula el total de la compra.
                # Esto evita que cada DetalleCompra.save() dispare un compra.save() intermedio
                # mientras el estado de la compra aún es 'aprobada', lo que crearía una ventana
                # de inconsistencia transitoria dentro de la misma transacción atómica.
                # El total se calcula explícitamente más abajo, antes del único compra.save() final.
                from django.db.models.signals import post_save, post_delete
                from compras.models import actualizar_total_compra
                post_save.disconnect(actualizar_total_compra, sender=DetalleCompra)
                post_delete.disconnect(actualizar_total_compra, sender=DetalleCompra)
                try:
                    formset.save()
                finally:
                    post_save.connect(actualizar_total_compra, sender=DetalleCompra)
                    post_delete.connect(actualizar_total_compra, sender=DetalleCompra)

                recepcion = form_recepcion.save(commit=False)

                # Incrementar stock con lock por producto para evitar condición de carrera
                for detalle in compra.detalles.select_related('producto').all():
                    if detalle.cantidad_recibida > 0:
                        prod = (
                            Producto.objects
                            .select_for_update()
                            .get(pk=detalle.producto_id)
                        )
                        prod.stock_actual += detalle.cantidad_recibida
                        prod.save(update_fields=['stock_actual'])

                        MovimientoInventario.objects.create(
                            producto=prod,
                            tipo='entrada',
                            cantidad=detalle.cantidad_recibida,
                            motivo=f'Recepción {compra.numero_referencia} — {compra.proveedor.nombre}',
                            usuario=request.user,
                        )

                # Asignamos todos los campos de recepción ANTES de cualquier save().
                # ORDEN CORRECTO:
                # 1. Calcular el total en memoria (sin persistir aún)
                # 2. Asignar todos los campos de estado y recepción
                # 3. Un único save() que persiste todo de forma atómica.
                # Esto elimina la ventana donde la BD quedaría con total calculado
                # pero estado='aprobada' si hubiera un crash entre operaciones.
                resultado = compra.detalles.aggregate(t=Sum('subtotal'))['t']
                compra.total = resultado or Decimal('0.00')

                tasa_obj = TasaCambio.tasa_vigente()
                tasa     = tasa_obj.tasa_bs_usd if tasa_obj else None

                compra.estado            = 'recibida'
                compra.fecha_recepcion   = recepcion.fecha_recepcion or timezone.now()
                compra.modalidad_pago    = recepcion.modalidad_pago
                compra.fecha_vencimiento = recepcion.fecha_vencimiento
                compra.pagado            = recepcion.modalidad_pago == 'contado'

                # Un solo save() persiste total + estado + todos los campos de recepción
                compra.save()

                if not compra.pagado:
                    cpp = CuentaPorPagar(
                        proveedor        = compra.proveedor,
                        compra           = compra,
                        saldo_restante   = compra.total,
                        fecha_vencimiento = compra.fecha_vencimiento,
                        registrada_por   = request.user,
                    )
                    cpp.fijar_conversion(compra.total, tasa)
                    cpp.save()

            AuditoriaAccion.registrar(
                usuario=request.user, accion='recibir_compra',
                descripcion=f'Recepción registrada: {compra.numero_referencia}. Pago: {compra.get_modalidad_pago_display()}. Ref: {compra.referencia_documento}',
                request=request, objeto_tipo='Compra', objeto_id=compra.pk,
            )

            messages.success(
                request,
                'Recepción registrada. Stock actualizado. ' +
                ('Cuenta por pagar generada.' if compra.modalidad_pago == 'credito' else 'Pago registrado al contado.')
            )
            return redirect('compras:detalle_compra', pk=compra.pk)
        else:
            messages.error(request, 'Revisa los errores antes de continuar.')
    else:
        form_recepcion = RecepcionCompraForm(instance=compra)
        formset        = RecepcionFormSet(queryset=detalles)

    return render(request, 'compras/recibir_compra.html', {
        'compra':          compra,
        'detalles':        detalles,
        'form_recepcion':  form_recepcion,
        'formset':         formset,
        'formset_detalle': zip(formset, detalles),
    })


# ─────────────────────────────────────────────
# CANCELAR COMPRA (Órdenes Inactivas)
# ─────────────────────────────────────────────
@login_requerido
def cancelar_compra(request, pk):
    compra = get_object_or_404(Compra, pk=pk)

    if compra.estado not in ['pendiente']:
        messages.error(request, 'Solo se pueden cancelar órdenes pendientes.')
        return redirect('compras:detalle_compra', pk=pk)

    if not request.user.es_admin() and compra.creada_por != request.user:
        messages.error(request, 'No tienes permiso para cancelar esta orden.')
        return redirect('compras:lista_compras')

    if request.method == 'POST':
        compra.estado = 'cancelada'
        compra.save()
        
        AuditoriaAccion.registrar(
            usuario=request.user, accion='cancelar_compra',
            descripcion=f'Orden {compra.numero_referencia} cancelada.',
            request=request, objeto_tipo='Compra', objeto_id=compra.pk,
        )
        messages.warning(request, f'Orden {compra.numero_referencia} cancelada.')
        return redirect('compras:lista_compras')

    return render(request, 'compras/cancelar_compra.html', {'compra': compra})