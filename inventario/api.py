from django.http import JsonResponse
from .models import Producto
from .decorators import login_requerido


@login_requerido
def api_sugerencia_cantidad(request):
    """Devuelve la cantidad sugerida de pedido para un producto."""
    producto_id = request.GET.get('producto')
    if not producto_id:
        return JsonResponse({'error': 'Falta producto'}, status=400)
    try:
        producto = Producto.objects.get(pk=producto_id, activo=True)
        return JsonResponse({'sugerencia': producto.cantidad_sugerida_pedido})
    except (Producto.DoesNotExist, ValueError):
        return JsonResponse({'error': 'Producto no encontrado'}, status=404)


@login_requerido
def api_producto_info(request):
    """
    Devuelve info del producto para autocompletar formularios.
    Usado tanto en ventas (precio_venta) como en compras (precio_compra).
    """
    producto_id = request.GET.get('producto')
    if not producto_id:
        return JsonResponse({'error': 'Falta producto'}, status=400)
    try:
        p = Producto.objects.get(pk=producto_id, activo=True)
        return JsonResponse({
            'stock':          p.stock_actual,
            'precio_venta':   str(p.precio_venta),
            'precio_compra':  str(p.precio_compra),
            'en_tendencia':   getattr(p, 'en_tendencia', False),
        })
    except (Producto.DoesNotExist, ValueError):
        return JsonResponse({'error': 'No encontrado'}, status=404)
