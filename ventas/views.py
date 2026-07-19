# ══════════════════════════════════════════════════════════════
# VIEWS — Módulo Ventas
# ══════════════════════════════════════════════════════════════

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Sum
from decimal import Decimal

from .models import Venta, DetalleVenta
from .forms  import VentaForm, DetalleVentaFormSet
from core.models             import AuditoriaAccion, TasaCambio
from core.models_bimonetario import CuentaPorCobrar
from core.decorators_core    import login_requerido, solo_admin
from inventario.models       import MovimientoInventario, Producto


# ─────────────────────────────────────────────
# LISTA
# ─────────────────────────────────────────────

@login_requerido
def lista_ventas(request):
    from django.core.paginator import Paginator

    estado = request.GET.get('estado', '')
    q      = request.GET.get('q', '')
    fecha  = request.GET.get('fecha', '')

    qs = Venta.objects.select_related('empleado', 'cliente')

    if not request.user.es_admin():
        qs = qs.filter(empleado=request.user)
    if estado:
        qs = qs.filter(estado=estado)
    if q:
        qs = qs.filter(
            Q(numero_factura__icontains=q) |
            Q(cliente__nombre__icontains=q) |
            Q(cliente__apellido__icontains=q) |
            Q(cliente__cedula_rif__icontains=q)
        )
    if fecha:
        qs = qs.filter(fecha=fecha)

    qs = qs.order_by('-fecha', '-hora')

    # ── Exportar a Excel (respeta filtros activos) ──
    # Se acepta también 'csv' como alias por compatibilidad con enlaces o
    # marcadores antiguos, pero siempre se entrega un .xlsx real — ya no
    # se genera CSV en ningún caso.
    if request.GET.get('export') in ('excel', 'csv'):
        from core.excel_utils import exportar_excel
        headers = [
            'N° Factura', 'Fecha', 'Hora', 'Cliente', 'Cédula/RIF',
            'Empleado', 'Método Pago', 'Estado',
            'Subtotal Bs', 'IVA Bs', 'Total Bs', 'Total USD', 'Tasa BCV',
        ]
        filas = [
            [
                v.numero_factura,
                v.fecha.strftime('%d/%m/%Y'),
                v.hora.strftime('%H:%M') if v.hora else '',
                v.cliente.get_nombre_completo() if v.cliente else '',
                v.cliente.cedula_rif if v.cliente else '',
                v.empleado.get_nombre_completo() if v.empleado else '',
                v.get_metodo_pago_display(),
                v.get_estado_display(),
                v.subtotal_bs, v.iva_bs, v.total_bs,
                v.total_usd, v.tasa_bcv_momento,
            ]
            for v in qs
        ]
        return exportar_excel('Ventas', headers, filas, 'ventas.xlsx')

    # ── Totales del día (solo admin) ──
    totales = {}
    if request.user.es_admin():
        from datetime import date
        totales = Venta.objects.filter(
            fecha=date.today(),
            estado__in=['procesada', 'a_credito', 'pagada']
        ).aggregate(total_bs=Sum('total_bs'), total_usd=Sum('total_usd'))

    # ── Paginación ──
    params = request.GET.copy()
    params.pop('page', None)
    params.pop('export', None)
    filter_params = params.urlencode()

    paginator = Paginator(qs, 20)
    page_obj  = paginator.get_page(request.GET.get('page'))

    return render(request, 'ventas/lista_ventas.html', {
        'ventas':        page_obj,
        'page_obj':      page_obj,
        'filter_params': filter_params,
        'estado':        estado,
        'q':             q,
        'fecha':         fecha,
        'totales':       totales,
    })


# ─────────────────────────────────────────────
# CREAR VENTA
# ─────────────────────────────────────────────

@login_requerido
def crear_venta(request):
    tasa_obj = TasaCambio.tasa_vigente()

    if request.method == 'POST':
        form    = VentaForm(request.POST)
        formset = DetalleVentaFormSet(request.POST, prefix='detalleventa_set')

        form_ok    = form.is_valid()
        formset_ok = formset.is_valid()

        if form_ok and formset_ok:
            try:
                with transaction.atomic():
                    venta          = form.save(commit=False)
                    venta.empleado = request.user
                    # Estado según método de pago
                    venta.estado   = 'a_credito' if venta.metodo_pago == 'credito' else 'procesada'
                    # Fijar tasa del momento
                    venta.tasa_bcv_momento = tasa_obj.tasa_bs_usd if tasa_obj else None
                    venta.save()

                    formset.instance = venta
                    formset.save()

                    # Calcular totales desde los detalles
                    subtotal = venta.detalles.aggregate(t=Sum('subtotal'))['t'] or Decimal('0')
                    venta.subtotal_bs = subtotal
                    venta.calcular_totales()

                    # Decrementar stock con lock por producto para evitar condición de carrera
                    # y el caso de que el mismo producto aparezca en más de un renglón de la venta.
                    for detalle in venta.detalles.all():
                        prod = (
                            Producto.objects
                            .select_for_update()
                            .get(pk=detalle.producto_id)
                        )
                        if detalle.cantidad > prod.stock_actual:
                            raise ValueError(
                                f'Stock insuficiente para {prod.nombre}. '
                                f'Disponible: {prod.stock_actual}, solicitado: {detalle.cantidad}.'
                            )
                        prod.stock_actual -= detalle.cantidad
                        prod.save(update_fields=['stock_actual'])

                        MovimientoInventario.objects.create(
                            producto=prod,
                            tipo='salida',
                            cantidad=detalle.cantidad,
                            motivo=f'Venta {venta.numero_factura}',
                            usuario=request.user,
                        )

                    # Si es crédito → generar CuentaPorCobrar
                    if venta.es_credito():
                        cpc = CuentaPorCobrar(
                            venta               = venta,
                            cliente             = venta.cliente,
                            saldo_restante      = venta.total_bs,
                            fecha_venta         = venta.fecha,
                            fecha_estimada_pago = venta.fecha_estimada_pago,
                            registrada_por      = request.user,
                        )
                        cpc.fijar_conversion(venta.total_bs, venta.tasa_bcv_momento)
                        cpc.save()

                AuditoriaAccion.registrar(
                    usuario=request.user, accion='crear_venta',
                    descripcion=(
                        f'Venta {venta.numero_factura} — '
                        f'Bs. {venta.total_bs} — {venta.get_metodo_pago_display()}'
                    ),
                    request=request, objeto_tipo='Venta', objeto_id=venta.pk,
                )
                messages.success(
                    request,
                    f'Venta {venta.numero_factura} registrada correctamente.'
                    + (' Cuenta por cobrar generada.' if venta.es_credito() else '')
                )
                return redirect('ventas:detalle_venta', pk=venta.pk)

            except ValueError as e:
                messages.error(request, str(e))
        else:
            messages.error(request, 'Revisa los errores antes de continuar.')
    else:
        form    = VentaForm()
        formset = DetalleVentaFormSet(prefix='detalleventa_set')

    return render(request, 'ventas/form_venta.html', {
        'form':     form,
        'formset':  formset,
        'tasa_hoy': tasa_obj,
    })


# ─────────────────────────────────────────────
# DETALLE
# ─────────────────────────────────────────────

@login_requerido
def detalle_venta(request, pk):
    venta    = get_object_or_404(Venta, pk=pk)
    detalles = venta.detalles.select_related('producto').all()
    cuenta   = getattr(venta, 'cuenta_por_cobrar', None)

    if not request.user.es_admin() and venta.empleado != request.user:
        messages.error(request, 'No tienes acceso a esta venta.')
        return redirect('ventas:lista_ventas')

    return render(request, 'ventas/detalle_venta.html', {
        'venta':    venta,
        'detalles': detalles,
        'cuenta':   cuenta,
    })


# ─────────────────────────────────────────────
# FACTURA (imprimible)
# ─────────────────────────────────────────────

@login_requerido
def ver_factura(request, pk):
    venta    = get_object_or_404(Venta, pk=pk)
    detalles = venta.detalles.select_related('producto').all()

    if not request.user.es_admin() and venta.empleado != request.user:
        messages.error(request, 'No tienes acceso a esta factura.')
        return redirect('ventas:lista_ventas')

    return render(request, 'ventas/factura.html', {
        'venta':    venta,
        'detalles': detalles,
    })


# ─────────────────────────────────────────────
# CANCELAR VENTA (solo Admin)
# ─────────────────────────────────────────────

@solo_admin
def cancelar_venta(request, pk):
    venta = get_object_or_404(Venta, pk=pk)

    if venta.estado == 'cancelada':
        messages.info(request, 'Esta venta ya está cancelada.')
        return redirect('ventas:detalle_venta', pk=pk)

    if request.method == 'POST':
        with transaction.atomic():
            # Revertir stock con lock por producto para evitar condición de carrera
            for detalle in venta.detalles.all():
                prod = (
                    Producto.objects
                    .select_for_update()
                    .get(pk=detalle.producto_id)
                )
                prod.stock_actual += detalle.cantidad
                prod.save(update_fields=['stock_actual'])
                MovimientoInventario.objects.create(
                    producto=prod,
                    tipo='entrada',
                    cantidad=detalle.cantidad,
                    motivo=f'Cancelación venta {venta.numero_factura}',
                    usuario=request.user,
                )

            # Cancelar cuenta por cobrar si existe
            cuenta = getattr(venta, 'cuenta_por_cobrar', None)
            if cuenta and cuenta.estado != 'saldada':
                cuenta.saldo_restante = Decimal('0.00')
                cuenta.estado = 'saldada'
                cuenta.save(update_fields=['saldo_restante', 'estado'])

            venta.estado = 'cancelada'
            venta.save(update_fields=['estado'])

        AuditoriaAccion.registrar(
            usuario=request.user, accion='cancelar_venta',
            descripcion=f'Venta {venta.numero_factura} cancelada. Stock revertido.',
            request=request, objeto_tipo='Venta', objeto_id=venta.pk,
        )
        messages.warning(request, f'Venta {venta.numero_factura} cancelada. Stock repuesto.')
        return redirect('ventas:lista_ventas')

    return render(request, 'ventas/cancelar_venta.html', {'venta': venta})


# ─────────────────────────────────────────────
# API: stock disponible de un producto
# ─────────────────────────────────────────────

@login_requerido
def api_stock_producto(request):
    from django.http import JsonResponse
    pid = request.GET.get('producto', '').strip()

    # En PostgreSQL un pk no numérico lanza ValueError antes de llegar a DoesNotExist.
    # Validamos antes de tocar el ORM para devolver siempre JSON controlado.
    if not pid or not pid.isdigit():
        return JsonResponse({'error': 'Parámetro inválido'}, status=400)

    try:
        p = Producto.objects.get(pk=int(pid), activo=True)
        return JsonResponse({
            'stock':        p.stock_actual,
            'precio_venta': str(p.precio_venta),
            'en_tendencia': getattr(p, 'en_tendencia', False),
        })
    except Producto.DoesNotExist:
        return JsonResponse({'error': 'No encontrado'}, status=404)
