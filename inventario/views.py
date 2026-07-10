from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, F

from inventario.models import (
    Producto, Categoria, Proveedor,
    SolicitudInventario, MovimientoInventario
)
from .forms import (
    ProductoForm, CategoriaForm, ProveedorForm,
    SolicitudInventarioForm, ResponderSolicitudForm
)
from inventario.decorators import solo_admin, login_requerido
from core.models import AuditoriaAccion


# ─────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────

@login_requerido
def dashboard(request):
    productos_bajo_stock = Producto.objects.filter(
        activo=True, stock_actual__lte=F('stock_minimo')
    ).order_by('stock_actual')

    solicitudes_pendientes = SolicitudInventario.objects.filter(
        estado='pendiente'
    ).count() if request.user.es_admin() else SolicitudInventario.objects.filter(
        estado='pendiente', empleado=request.user
    ).count()

    total_productos = Producto.objects.filter(activo=True).count()

    context = {
        'productos_bajo_stock':    productos_bajo_stock,
        'solicitudes_pendientes':  solicitudes_pendientes,
        'total_productos':         total_productos,
    }
    return render(request, 'inventario/dashboard.html', context)


# ─────────────────────────────────────────────
# PRODUCTOS
# ─────────────────────────────────────────────

@login_requerido
def lista_productos(request):
    import csv
    from django.http import HttpResponse
    from django.core.paginator import Paginator

    query      = request.GET.get('q', '')
    categoria  = request.GET.get('categoria', '')
    solo_bajos = request.GET.get('bajo_stock', '')

    qs = Producto.objects.filter(activo=True).select_related('categoria', 'proveedor')

    if query:
        qs = qs.filter(
            Q(nombre__icontains=query) | Q(codigo__icontains=query)
        )
    if categoria:
        qs = qs.filter(categoria_id=categoria)
    if solo_bajos:
        qs = qs.filter(stock_actual__lte=F('stock_minimo'))

    qs = qs.order_by('nombre')

    # ── Exportar CSV ──
    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
        response['Content-Disposition'] = 'attachment; filename="productos.csv"'
        writer = csv.writer(response)
        writer.writerow([
            'Código', 'Nombre', 'Categoría', 'Proveedor',
            'Precio Compra Bs', 'Precio Venta Bs',
            'Stock Actual', 'Stock Mínimo', 'Estado',
        ])
        for p in qs:
            writer.writerow([
                p.codigo or '',
                p.nombre,
                p.categoria.nombre if p.categoria else '',
                p.proveedor.nombre if p.proveedor else '',
                p.precio_compra,
                p.precio_venta,
                p.stock_actual,
                p.stock_minimo,
                'Activo' if p.activo else 'Inactivo',
            ])
        return response

    categorias = Categoria.objects.all()

    # ── Paginación ──
    params = request.GET.copy()
    params.pop('page', None)
    params.pop('export', None)
    filter_params = params.urlencode()

    paginator = Paginator(qs, 25)
    page_obj  = paginator.get_page(request.GET.get('page'))

    return render(request, 'inventario/lista_productos.html', {
        'productos':     page_obj,
        'page_obj':      page_obj,
        'filter_params': filter_params,
        'categorias':    categorias,
        'query':         query,
    })


@login_requerido
def detalle_producto(request, pk):
    producto    = get_object_or_404(Producto, pk=pk)
    movimientos = MovimientoInventario.objects.filter(
        producto=producto
    ).order_by('-fecha')[:20]

    return render(request, 'inventario/detalle_producto.html', {
        'producto':    producto,
        'movimientos': movimientos,
    })


@solo_admin
def crear_producto(request):
    if request.method == 'POST':
        form = ProductoForm(request.POST)
        if form.is_valid():
            producto = form.save()
            # Registrar movimiento inicial si hay stock
            if producto.stock_actual > 0:
                MovimientoInventario.objects.create(
                    producto=producto,
                    tipo='entrada',
                    cantidad=producto.stock_actual,
                    motivo='Stock inicial al crear el producto',
                    usuario=request.user,
                )
            AuditoriaAccion.registrar(
                usuario=request.user, accion='crear_producto',
                descripcion=f'Producto creado: {producto.nombre} (código: {producto.codigo})',
                request=request, objeto_tipo='Producto', objeto_id=producto.pk,
            )
            messages.success(request, f'Producto "{producto.nombre}" creado correctamente.')
            return redirect('inventario:lista_productos')
    else:
        form = ProductoForm()

    return render(request, 'inventario/form_producto.html', {
        'form':   form,
        'titulo': 'Nuevo producto',
        'accion': 'Crear',
    })


@solo_admin
def editar_producto(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    stock_anterior = producto.stock_actual

    if request.method == 'POST':
        form = ProductoForm(request.POST, instance=producto)
        if form.is_valid():
            producto = form.save()
            # Registrar ajuste si cambió el stock manualmente
            diferencia = producto.stock_actual - stock_anterior
            if diferencia != 0:
                MovimientoInventario.objects.create(
                    producto=producto,
                    tipo='ajuste',
                    cantidad=abs(diferencia),
                    motivo=f'Ajuste manual desde edición ({"+" if diferencia > 0 else ""}{diferencia})',
                    usuario=request.user,
                )
                AuditoriaAccion.registrar(
                    usuario=request.user, accion='ajuste_stock',
                    descripcion=f'Ajuste de stock en {producto.nombre}: {stock_anterior} → {producto.stock_actual} (Δ{diferencia:+d})',
                    request=request, objeto_tipo='Producto', objeto_id=producto.pk,
                )
            AuditoriaAccion.registrar(
                usuario=request.user, accion='editar_producto',
                descripcion=f'Producto editado: {producto.nombre} (código: {producto.codigo})',
                request=request, objeto_tipo='Producto', objeto_id=producto.pk,
            )
            messages.success(request, f'Producto "{producto.nombre}" actualizado.')
            return redirect('inventario:detalle_producto', pk=producto.pk)
    else:
        form = ProductoForm(instance=producto)

    return render(request, 'inventario/form_producto.html', {
        'form':     form,
        'titulo':   f'Editar: {producto.nombre}',
        'accion':   'Guardar cambios',
        'producto': producto,
    })


@solo_admin
def desactivar_producto(request, pk):
    producto = get_object_or_404(Producto, pk=pk, activo=True)

    if request.method == 'POST':
        producto.activo = False
        producto.save(update_fields=['activo'])
        messages.warning(request, f'Producto "{producto.nombre}" desactivado.')
        return redirect('inventario:lista_productos')

    # GET → mostrar confirmación antes de ejecutar
    return render(request, 'inventario/confirmar_desactivar.html', {'producto': producto})


# ─────────────────────────────────────────────
# CATEGORÍAS
# ─────────────────────────────────────────────

@solo_admin
def lista_categorias(request):
    categorias = Categoria.objects.all().order_by('nombre')
    return render(request, 'inventario/lista_categorias.html', {'categorias': categorias})


@solo_admin
def crear_categoria(request):
    if request.method == 'POST':
        form = CategoriaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Categoría creada.')
            return redirect('inventario:lista_categorias')
    else:
        form = CategoriaForm()
    return render(request, 'inventario/form_categoria.html', {'form': form, 'titulo': 'Nueva categoría'})


@solo_admin
def editar_categoria(request, pk):
    categoria = get_object_or_404(Categoria, pk=pk)
    if request.method == 'POST':
        form = CategoriaForm(request.POST, instance=categoria)
        if form.is_valid():
            form.save()
            messages.success(request, 'Categoría actualizada.')
            return redirect('inventario:lista_categorias')
    else:
        form = CategoriaForm(instance=categoria)
    return render(request, 'inventario/form_categoria.html', {
        'form': form, 'titulo': f'Editar: {categoria.nombre}'
    })


# ─────────────────────────────────────────────
# PROVEEDORES
# ─────────────────────────────────────────────

@solo_admin
def lista_proveedores(request):
    proveedores = Proveedor.objects.all().order_by('nombre')
    return render(request, 'inventario/lista_proveedores.html', {'proveedores': proveedores})


@solo_admin
def crear_proveedor(request):
    if request.method == 'POST':
        form = ProveedorForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Proveedor registrado.')
            return redirect('inventario:lista_proveedores')
    else:
        form = ProveedorForm()
    return render(request, 'inventario/form_proveedor.html', {'form': form, 'titulo': 'Nuevo proveedor'})


@solo_admin
def editar_proveedor(request, pk):
    proveedor = get_object_or_404(Proveedor, pk=pk)
    if request.method == 'POST':
        form = ProveedorForm(request.POST, instance=proveedor)
        if form.is_valid():
            form.save()
            messages.success(request, 'Proveedor actualizado.')
            return redirect('inventario:lista_proveedores')
    else:
        form = ProveedorForm(instance=proveedor)
    return render(request, 'inventario/form_proveedor.html', {
        'form': form, 'titulo': f'Editar: {proveedor.nombre}'
    })


# ─────────────────────────────────────────────
# SOLICITUDES DE INVENTARIO
# ─────────────────────────────────────────────

@login_requerido
def lista_solicitudes(request):
    from django.core.paginator import Paginator

    if request.user.es_admin():
        qs = SolicitudInventario.objects.all().select_related(
            'empleado', 'producto', 'admin'
        ).order_by('-fecha_solicitud')
    else:
        qs = SolicitudInventario.objects.filter(
            empleado=request.user
        ).select_related('producto', 'admin').order_by('-fecha_solicitud')

    params = request.GET.copy()
    params.pop('page', None)
    filter_params = params.urlencode()

    paginator = Paginator(qs, 20)
    page_obj  = paginator.get_page(request.GET.get('page'))

    return render(request, 'inventario/lista_solicitudes.html', {
        'solicitudes':   page_obj,
        'page_obj':      page_obj,
        'filter_params': filter_params,
    })


@login_requerido
def crear_solicitud(request):
    if request.user.es_admin():
        messages.info(request, 'El admin gestiona directamente el inventario.')
        return redirect('inventario:lista_productos')

    sugerencia = None   # Inicializar siempre; evita NameError y el antipatrón 'in locals()'

    if request.method == 'POST':
        form = SolicitudInventarioForm(request.POST)
        if form.is_valid():
            solicitud = form.save(commit=False)
            solicitud.empleado = request.user
            solicitud.save()
            messages.success(request, 'Solicitud enviada al administrador.')
            return redirect('inventario:lista_solicitudes')
    else:
        # Pre-seleccionar producto si viene por URL
        producto_id = request.GET.get('producto')

        # En PostgreSQL un pk no numérico lanza ValueError/DataError antes de
        # llegar a DoesNotExist. Validamos antes de tocar el ORM.
        if producto_id and not producto_id.isdigit():
            producto_id = None

        form = SolicitudInventarioForm(initial={'producto': producto_id} if producto_id else {})

        if producto_id:
            try:
                p = Producto.objects.get(pk=producto_id, activo=True)
                sugerencia = p.cantidad_sugerida_pedido
            except Producto.DoesNotExist:
                pass

    return render(request, 'inventario/form_solicitud.html', {
        'form':      form,
        'sugerencia': sugerencia,
    })


@solo_admin
def responder_solicitud(request, pk):
    solicitud = get_object_or_404(SolicitudInventario, pk=pk, estado='pendiente')

    if request.method == 'POST':
        form = ResponderSolicitudForm(request.POST)
        if form.is_valid():
            decision    = form.cleaned_data['decision']
            observacion = form.cleaned_data['observacion']

            with transaction.atomic():
                solicitud.estado          = decision
                solicitud.admin           = request.user
                solicitud.observacion     = observacion
                solicitud.fecha_respuesta = timezone.now()
                solicitud.save()

                # Si se aprueba: actualizar stock dentro de la misma transacción
                # con lock para evitar condición de carrera
                if decision == 'aprobada':
                    producto = (
                        Producto.objects
                        .select_for_update()
                        .get(pk=solicitud.producto_id)
                    )
                    producto.stock_actual += solicitud.cantidad_solicitada
                    producto.save(update_fields=['stock_actual'])

                    MovimientoInventario.objects.create(
                        producto=producto,
                        tipo='entrada',
                        cantidad=solicitud.cantidad_solicitada,
                        motivo=f'Solicitud #{solicitud.id} aprobada por {request.user.username}',
                        usuario=request.user,
                    )
                    messages.success(request, f'Solicitud aprobada. Stock de "{producto.nombre}" actualizado.')
                else:
                    messages.warning(request, 'Solicitud rechazada.')

            return redirect('inventario:lista_solicitudes')
    else:
        form = ResponderSolicitudForm()

    return render(request, 'inventario/responder_solicitud.html', {
        'solicitud': solicitud,
        'form':      form,
    })
