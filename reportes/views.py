# ══════════════════════════════════════════════════════════════
# VIEWS — Módulo Reportes
# ══════════════════════════════════════════════════════════════

import logging
from django.shortcuts import render, redirect
from django.contrib import messages
from datetime import date, timedelta

from .engine import (
    calcular_tendencias, panel_abastecimiento,
    reporte_ventas, reporte_compras, reporte_inventario,
)
from core.decorators_core import solo_admin
from core.models import TasaCambio

logger = logging.getLogger(__name__)


def _rango_fechas(request):
    """Extrae fecha_inicio y fecha_fin del GET, con defaults al mes actual."""
    hoy    = date.today()
    inicio = request.GET.get('fecha_inicio') or hoy.replace(day=1).isoformat()
    fin    = request.GET.get('fecha_fin')    or hoy.isoformat()
    try:
        from datetime import date as dt
        inicio = dt.fromisoformat(inicio)
        fin    = dt.fromisoformat(fin)
    except ValueError:
        inicio = hoy.replace(day=1)
        fin    = hoy
    # Garantizar orden correcto
    if inicio > fin:
        inicio, fin = fin, inicio
    return inicio, fin


# ─────────────────────────────────────────────
# ÍNDICE DE REPORTES
# ─────────────────────────────────────────────

@solo_admin
def index(request):
    tasa = TasaCambio.tasa_vigente()
    return render(request, 'reportes/index.html', {'tasa': tasa})


# ─────────────────────────────────────────────
# PANEL DE TENDENCIAS Y ABASTECIMIENTO
# ─────────────────────────────────────────────

@solo_admin
def tendencias(request):
    # Recalcular tendencias al abrir el panel
    resultados = calcular_tendencias()

    en_tendencia  = [r for r in resultados if r['en_tendencia']]
    sin_tendencia = [r for r in resultados if not r['en_tendencia'] and r['vol_rc'] > 0]

    return render(request, 'reportes/tendencias.html', {
        'resultados':      resultados,
        'en_tendencia':    en_tendencia,
        'sin_tendencia':   sin_tendencia,
        'total_analizado': len(resultados),
    })


@solo_admin
def abastecimiento(request):
    from inventario.models import Proveedor
    proveedor_id = request.GET.get('proveedor', '')
    proveedores  = Proveedor.objects.all().order_by('nombre')
    criticos     = panel_abastecimiento(proveedor_id or None)

    return render(request, 'reportes/abastecimiento.html', {
        'criticos':     criticos,
        'proveedores':  proveedores,
        'proveedor_id': proveedor_id,
    })


# ─────────────────────────────────────────────
# REPORTE DE VENTAS
# ─────────────────────────────────────────────

@solo_admin
def rep_ventas(request):
    inicio, fin = _rango_fechas(request)
    q = request.GET.get('q', '').strip()

    # Valores por defecto en caso de error
    datos = {
        'totales':       {'total_bs': None, 'total_usd': None, 'cantidad': 0},
        'por_dia':       [],
        'top_productos': [],
        'por_metodo':    [],
        'fecha_inicio':  inicio,
        'fecha_fin':     fin,
        'q':             q,
    }

    try:
        datos = reporte_ventas(inicio, fin, q=q or None)
    except Exception:
        logger.exception('Error generando reporte de ventas [%s – %s]', inicio, fin)
        messages.warning(request, 'Ocurrió un error al cargar el reporte. Se muestran datos parciales.')

    try:
        tasa = TasaCambio.tasa_vigente()
        valor_tasa = getattr(tasa, 'tasa_bs_usd', 1) or 1
    except Exception:
        tasa = None
        valor_tasa = 1

    return render(request, 'reportes/ventas.html', {
        **datos,
        'tasa':       tasa,
        'valor_tasa': valor_tasa,
    })


# ─────────────────────────────────────────────
# REPORTE DE COMPRAS
# ─────────────────────────────────────────────

@solo_admin
def rep_compras(request):
    from inventario.models import Proveedor
    inicio, fin  = _rango_fechas(request)
    proveedor_id = request.GET.get('proveedor', '') or None

    datos = {
        'totales':          {'total_bs': None, 'cantidad': 0},
        'por_proveedor':    [],
        'pendientes_pago':  0,
        'fecha_inicio':     inicio,
        'fecha_fin':        fin,
        'proveedor_id':     proveedor_id or '',
    }

    try:
        datos = reporte_compras(inicio, fin, proveedor_id=proveedor_id)
    except Exception:
        logger.exception('Error generando reporte de compras [%s – %s]', inicio, fin)
        messages.warning(request, 'Ocurrió un error al cargar el reporte. Se muestran datos parciales.')

    proveedores = Proveedor.objects.filter(activo=True).order_by('nombre')
    return render(request, 'reportes/compras.html', {
        **datos,
        'proveedores': proveedores,
    })


# ─────────────────────────────────────────────
# REPORTE DE INVENTARIO
# ─────────────────────────────────────────────

@solo_admin
def rep_inventario(request):
    try:
        datos = reporte_inventario()
    except Exception:
        logger.exception('Error generando reporte de inventario')
        messages.warning(request, 'Ocurrió un error al cargar el reporte de inventario.')
        datos = {
            'productos':       [],
            'valorizacion':    0,
            'bajo_stock':      [],
            'en_tendencia':    [],
            'por_categoria':   [],
            'total_productos': 0,
        }
    return render(request, 'reportes/inventario.html', {**datos})


# ─────────────────────────────────────────────
# REPORTE FINANCIERO (cuentas por cobrar/pagar)
# ─────────────────────────────────────────────

@solo_admin
def rep_financiero(request):
    from core.models_bimonetario import CuentaPorCobrar, CuentaPorPagar
    from django.db.models import Sum, Count, Q

    hoy = date.today()

    try:
        cobrar = CuentaPorCobrar.objects.filter(estado__in=['pendiente', 'abonada'])
        pagar  = CuentaPorPagar.objects.filter(estado__in=['pendiente', 'abonada'])

        resumen_cobrar = cobrar.aggregate(
            total_bs  = Sum('saldo_restante'),
            total_usd = Sum('monto_usd'),
            cantidad  = Count('id'),
            vencidas  = Count('id', filter=Q(fecha_estimada_pago__lt=hoy)),
        )
        resumen_pagar = pagar.aggregate(
            total_bs  = Sum('saldo_restante'),
            total_usd = Sum('monto_usd'),
            cantidad  = Count('id'),
            vencidas  = Count('id', filter=Q(fecha_vencimiento__lt=hoy)),
        )

        tasa = TasaCambio.tasa_vigente()

        return render(request, 'reportes/financiero.html', {
            'cobrar':         cobrar.select_related('cliente', 'venta').order_by('fecha_estimada_pago'),
            'pagar':          pagar.select_related('proveedor', 'compra').order_by('fecha_vencimiento'),
            'resumen_cobrar': resumen_cobrar,
            'resumen_pagar':  resumen_pagar,
            'tasa':           tasa,
        })

    except Exception:
        logger.exception('Error generando reporte financiero')
        messages.warning(request, 'Ocurrió un error al cargar el reporte financiero.')
        return render(request, 'reportes/financiero.html', {
            'cobrar':         [],
            'pagar':          [],
            'resumen_cobrar': {'total_bs': None, 'total_usd': None, 'cantidad': 0, 'vencidas': 0},
            'resumen_pagar':  {'total_bs': None, 'total_usd': None, 'cantidad': 0, 'vencidas': 0},
            'tasa':           None,
        })
