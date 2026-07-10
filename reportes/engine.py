# ══════════════════════════════════════════════════════════════
# ENGINE — Motor de tendencias y cálculos DSS
# Consumido por las vistas de reportes
# ══════════════════════════════════════════════════════════════

from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal


# ─────────────────────────────────────────────
# 1. ALGORITMO DE VELOCIDAD DE VENTA
# Rango Corto (RC): últimos 7 días
# Rango Largo (RL): 21 días previos al RC
# Condición tendencia: vol_RC > promedio_semanal_RL * 1.20
#
# OPTIMIZADO: 3 queries totales en lugar de N*3
# (una por RC, una por RL, un bulk_update al final)
# ─────────────────────────────────────────────

def calcular_tendencias():
    """
    Recorre todos los productos activos, aplica el algoritmo
    de velocidad de venta y actualiza el campo en_tendencia.
    Retorna lista de dicts con métricas por producto.
    """
    from inventario.models import Producto
    from ventas.models import DetalleVenta

    hoy       = date.today()
    inicio_rc = hoy - timedelta(days=7)
    inicio_rl = hoy - timedelta(days=28)   # 21 días antes del inicio del RC
    fin_rl    = inicio_rc - timedelta(days=1)

    productos = list(
        Producto.objects.filter(activo=True)
        .select_related('categoria', 'proveedor')
    )

    if not productos:
        return []

    ids = [p.id for p in productos]

    # ── Una sola query para todos los volúmenes RC ──
    rc_rows = (
        DetalleVenta.objects.filter(
            producto_id__in=ids,
            venta__fecha__gte=inicio_rc,
            venta__estado__in=['procesada', 'a_credito', 'pagada']
        )
        .values('producto_id')
        .annotate(total=Sum('cantidad'))
    )
    rc_map = {r['producto_id']: r['total'] for r in rc_rows}

    # ── Una sola query para todos los volúmenes RL ──
    rl_rows = (
        DetalleVenta.objects.filter(
            producto_id__in=ids,
            venta__fecha__gte=inicio_rl,
            venta__fecha__lte=fin_rl,
            venta__estado__in=['procesada', 'a_credito', 'pagada']
        )
        .values('producto_id')
        .annotate(total=Sum('cantidad'))
    )
    rl_map = {r['producto_id']: r['total'] for r in rl_rows}

    # ── Calcular métricas y recolectar IDs a actualizar ──
    ids_tendencia_on  = []
    ids_tendencia_off = []
    resultados = []

    for producto in productos:
        vol_rc = rc_map.get(producto.id, 0)
        vol_rl = rl_map.get(producto.id, 0)

        promedio_semanal_rl = Decimal(str(vol_rl)) / Decimal('3')
        umbral              = promedio_semanal_rl * Decimal('1.20')
        en_tendencia        = bool(vol_rc > umbral and vol_rc > 0)

        if producto.en_tendencia != en_tendencia:
            if en_tendencia:
                ids_tendencia_on.append(producto.id)
            else:
                ids_tendencia_off.append(producto.id)

        # Proyección lineal para 2 semanas
        promedio_diario         = Decimal(str(vol_rc)) / Decimal('7')
        cantidad_sugerida_2sem  = max(
            int((promedio_diario * 14) - producto.stock_actual),
            producto.stock_minimo
        )

        resultados.append({
            'producto':              producto,
            'vol_rc':                vol_rc,
            'vol_rl':                vol_rl,
            'promedio_semanal_rl':   round(float(promedio_semanal_rl), 2),
            'umbral':                round(float(umbral), 2),
            'en_tendencia':          en_tendencia,
            'cantidad_sugerida_2sem': cantidad_sugerida_2sem,
        })

    # ── Bulk-update en 2 queries en lugar de N saves individuales ──
    if ids_tendencia_on:
        Producto.objects.filter(id__in=ids_tendencia_on).update(en_tendencia=True)
    if ids_tendencia_off:
        Producto.objects.filter(id__in=ids_tendencia_off).update(en_tendencia=False)

    return sorted(resultados, key=lambda x: x['vol_rc'], reverse=True)


# ─────────────────────────────────────────────
# 2. PANEL DE ABASTECIMIENTO CRÍTICO
# Productos en tendencia o bajo stock por proveedor
#
# OPTIMIZADO: 1 query batch para volúmenes de 7 días
# ─────────────────────────────────────────────

def panel_abastecimiento(proveedor_id=None):
    """
    Retorna productos que necesitan reposición urgente,
    agrupados por proveedor, con cantidad sugerida para 2 semanas.
    """
    from inventario.models import Producto
    from ventas.models import DetalleVenta

    hoy    = date.today()
    hace_7 = hoy - timedelta(days=7)

    qs = Producto.objects.filter(activo=True).select_related('proveedor', 'categoria')
    if proveedor_id:
        qs = qs.filter(proveedor_id=proveedor_id)

    # Pre-filtrar candidatos críticos en Python para reducir el batch posterior
    todos        = list(qs)
    criticos_raw = [
        p for p in todos
        if p.stock_actual <= p.stock_minimo or getattr(p, 'en_tendencia', False)
    ]

    if not criticos_raw:
        return []

    ids_criticos = [p.id for p in criticos_raw]

    # ── Una sola query para todos los volúmenes de 7 días ──
    vol_rows = (
        DetalleVenta.objects.filter(
            producto_id__in=ids_criticos,
            venta__fecha__gte=hace_7,
            venta__estado__in=['procesada', 'a_credito', 'pagada']
        )
        .values('producto_id')
        .annotate(t=Sum('cantidad'))
    )
    vol_map = {r['producto_id']: r['t'] for r in vol_rows}

    criticos = []
    for p in criticos_raw:
        bajo_stock   = p.stock_actual <= p.stock_minimo
        en_tendencia = getattr(p, 'en_tendencia', False)
        vol_7d       = vol_map.get(p.id, 0)

        prom_diario = Decimal(str(vol_7d)) / Decimal('7')
        sugerido    = max(int(prom_diario * 14) - p.stock_actual, p.stock_minimo)

        criticos.append({
            'producto':     p,
            'bajo_stock':   bajo_stock,
            'en_tendencia': en_tendencia,
            'vol_7d':       vol_7d,
            'sugerido':     sugerido,
        })

    return sorted(criticos, key=lambda x: (not x['en_tendencia'], x['producto'].stock_actual))


# ─────────────────────────────────────────────
# 3. REPORTE DE VENTAS POR PERÍODO
# ─────────────────────────────────────────────

def reporte_ventas(fecha_inicio, fecha_fin, q=None):
    from ventas.models import Venta, DetalleVenta
    from django.db.models import Q as DQ

    ventas = Venta.objects.filter(
        fecha__gte=fecha_inicio,
        fecha__lte=fecha_fin,
        estado__in=['procesada', 'a_credito', 'pagada']
    )

    if q:
        ventas = ventas.filter(
            DQ(numero_factura__icontains=q)     |
            DQ(cliente__nombre__icontains=q)     |
            DQ(cliente__apellido__icontains=q)   |
            DQ(cliente__cedula_rif__icontains=q)
        )

    totales = ventas.aggregate(
        total_bs  = Sum('total_bs'),
        total_usd = Sum('total_usd'),
        cantidad  = Count('id'),
    )

    # Ventas por día
    from django.db.models.functions import TruncDate
    por_dia = list(
        ventas
        .annotate(dia=TruncDate('fecha'))
        .values('dia')
        .annotate(total=Sum('total_bs'), cantidad=Count('id'))
        .order_by('dia')
    )

    # Top productos — FIX: filtra por venta__in=ventas para respetar el filtro q
    top_productos = list(
        DetalleVenta.objects
        .filter(venta__in=ventas)
        .values('producto__nombre', 'producto__codigo')
        .annotate(
            unidades = Sum('cantidad'),
            ingresos = Sum('subtotal'),
        )
        .order_by('-unidades')[:10]
    )

    # Por método de pago
    por_metodo = list(
        ventas
        .values('metodo_pago')
        .annotate(total=Sum('total_bs'), cantidad=Count('id'))
        .order_by('-total')
    )

    return {
        'totales':       totales,
        'por_dia':       por_dia,
        'top_productos': top_productos,
        'por_metodo':    por_metodo,
        'fecha_inicio':  fecha_inicio,
        'fecha_fin':     fecha_fin,
        'q':             q or '',
    }


# ─────────────────────────────────────────────
# 4. REPORTE DE COMPRAS POR PERÍODO
# ─────────────────────────────────────────────

def reporte_compras(fecha_inicio, fecha_fin, proveedor_id=None):
    from compras.models import Compra

    compras = Compra.objects.filter(
        fecha_creacion__date__gte=fecha_inicio,
        fecha_creacion__date__lte=fecha_fin,
        estado='recibida'
    ).select_related('proveedor')

    if proveedor_id:
        compras = compras.filter(proveedor_id=proveedor_id)

    totales = compras.aggregate(
        total_bs = Sum('total'),
        cantidad = Count('id'),
    )

    por_proveedor = list(
        compras
        .values('proveedor__nombre')
        .annotate(total=Sum('total'), cantidad=Count('id'))
        .order_by('-total')
    )

    pendientes_pago = (
        compras.filter(modalidad_pago='credito', pagado=False)
        .aggregate(deuda=Sum('total'))['deuda']
        or Decimal('0')
    )

    return {
        'totales':          totales,
        'por_proveedor':    por_proveedor,
        'pendientes_pago':  pendientes_pago,
        'fecha_inicio':     fecha_inicio,
        'fecha_fin':        fecha_fin,
        'proveedor_id':     proveedor_id or '',
    }


# ─────────────────────────────────────────────
# 5. REPORTE DE INVENTARIO
#
# OPTIMIZADO: cantidad_sugerida se calcula en batch
# (una sola query para todos los productos con bajo stock)
# El template recibe bajo_stock como lista de dicts:
#   {'producto': Producto, 'cantidad_sugerida': int}
# ─────────────────────────────────────────────

def reporte_inventario():
    from inventario.models import Producto
    from ventas.models import DetalleVenta
    from django.db.models import F, ExpressionWrapper, DecimalField

    productos = Producto.objects.filter(activo=True).select_related('categoria', 'proveedor')

    # Valoración patrimonial (stock * precio_compra)
    valorizacion = (
        productos
        .annotate(
            valor=ExpressionWrapper(
                F('stock_actual') * F('precio_compra'),
                output_field=DecimalField()
            )
        )
        .aggregate(total=Sum('valor'))['total'] or Decimal('0')
    )

    # Evaluación única del queryset; Django lo cachea internamente
    bajo_stock_prods = [p for p in productos if p.stock_bajo]
    en_tendencia     = [p for p in productos if getattr(p, 'en_tendencia', False)]

    # ── Batch: ventas últimos 7 días para todos los productos con bajo stock ──
    ventas_map = {}
    if bajo_stock_prods:
        ids_bajo = [p.id for p in bajo_stock_prods]
        hace_7   = date.today() - timedelta(days=7)
        rows = (
            DetalleVenta.objects.filter(
                producto_id__in=ids_bajo,
                venta__fecha__gte=hace_7,
                venta__estado__in=['procesada', 'a_credito', 'pagada']
            )
            .values('producto_id')
            .annotate(total=Sum('cantidad'))
        )
        ventas_map = {r['producto_id']: r['total'] for r in rows}

    # Construir lista enriquecida para el template
    bajo_stock = []
    for p in bajo_stock_prods:
        vendido         = ventas_map.get(p.id, 0)
        promedio_diario = vendido / 7
        necesario       = (promedio_diario * p.dias_cobertura) - p.stock_actual
        bajo_stock.append({
            'producto':         p,
            'cantidad_sugerida': max(int(necesario), p.stock_minimo),
        })

    por_categoria = list(
        productos
        .values('categoria__nombre')
        .annotate(cantidad=Count('id'), stock_total=Sum('stock_actual'))
        .order_by('-stock_total')
    )

    return {
        'productos':       productos,
        'valorizacion':    valorizacion,
        'bajo_stock':      bajo_stock,      # lista de dicts {producto, cantidad_sugerida}
        'en_tendencia':    en_tendencia,
        'por_categoria':   por_categoria,
        'total_productos': productos.count(),
    }
