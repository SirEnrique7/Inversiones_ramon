from django.db import models

class Categoria(models.Model):
    nombre              = models.CharField(max_length=100)
    descripcion         = models.TextField(blank=True)
    # ── Días de cobertura por defecto para productos de esta categoría ──
    # Si el producto no tiene valor propio, hereda éste. Si la categoría
    # tampoco lo tiene, el sistema usa el fallback global de 7 días.
    dias_cobertura_default = models.PositiveSmallIntegerField(
        null=True, blank=True, default=None,
        verbose_name='Días de cobertura predeterminados',
        help_text='Si se define aquí, los productos de la categoría sin valor '
                  'propio heredarán este número de días para calcular el pedido sugerido.'
    )

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name_plural = "Categorías"


class Proveedor(models.Model):
    DIA_CHOICES = [
        ('lunes',     'Lunes'),
        ('martes',    'Martes'),
        ('miercoles', 'Miércoles'),
        ('jueves',    'Jueves'),
        ('viernes',   'Viernes'),
        ('sabado',    'Sábado'),
    ]
    nombre     = models.CharField(max_length=150)
    rif        = models.CharField(max_length=20, unique=True)
    telefono   = models.CharField(max_length=20, blank=True)
    direccion  = models.TextField(blank=True)
    empresa    = models.CharField(max_length=150, blank=True)
    dia_visita = models.CharField(max_length=15, choices=DIA_CHOICES, blank=True)
    activo     = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nombre} ({self.rif})"


class Producto(models.Model):
    # Anotación de tipo para evitar que Pylance marque 'id' como desconocido
    id: int

    codigo         = models.CharField(max_length=20, unique=True, blank=True, null=True)
    nombre         = models.CharField(max_length=150)
    descripcion    = models.TextField(blank=True)
    precio_compra  = models.DecimalField(max_digits=12, decimal_places=2)
    precio_venta   = models.DecimalField(max_digits=12, decimal_places=2)
    stock_actual   = models.IntegerField(default=0)
    stock_minimo   = models.IntegerField(default=5)
    dias_cobertura = models.IntegerField(
        default=None, null=True, blank=True,
        verbose_name='Días de cobertura',
        help_text='Si se deja vacío, se hereda el valor de la categoría (o 7 días por defecto).'
    )
    categoria      = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True)
    proveedor      = models.ForeignKey(Proveedor, on_delete=models.SET_NULL, null=True)
    # db_index=True: 'activo' se usa como pre-filtro en casi toda consulta
    # de productos (dashboard, listas, panel de abastecimiento), siempre
    # junto a la comparación stock_actual <= stock_minimo.
    activo         = models.BooleanField(default=True, db_index=True)
    en_tendencia   = models.BooleanField(
        default=False,
        verbose_name='En tendencia',
        help_text='Actualizado por el motor de reportes automáticamente.'
    )

    def save(self, *args, **kwargs):
        # ── Tracking de cambios de precio ───────────────────────────────────
        # Capturamos los valores ANTES del save para detectar si cambiaron.
        # Sólo aplica en actualizaciones (no en inserciones nuevas).
        _usuario = kwargs.pop('usuario', None)
        precios_anteriores = {}
        if not self._state.adding and self.pk:
            try:
                anterior = Producto.objects.get(pk=self.pk)
                precios_anteriores = {
                    'compra': anterior.precio_compra,
                    'venta':  anterior.precio_venta,
                }
            except Producto.DoesNotExist:
                pass

        # En inserciones nuevas sin código, guardamos NULL para que el
        # UNIQUE de PostgreSQL no colisione mientras el pk no está asignado.
        if self._state.adding and not self.codigo:
            self.codigo = None
        super().save(*args, **kwargs)
        if not self.codigo:
            self.codigo = f"PROD-{self.id:04d}"
            Producto.objects.filter(pk=self.pk).update(codigo=self.codigo)

        # ── Registrar historial si los precios cambiaron ─────────────────────
        if precios_anteriores:
            registros = []
            if precios_anteriores['compra'] != self.precio_compra:
                registros.append(HistorialPrecio(
                    producto=self, tipo='compra',
                    precio_anterior=precios_anteriores['compra'],
                    precio_nuevo=self.precio_compra,
                    cambiado_por=_usuario,
                ))
            if precios_anteriores['venta'] != self.precio_venta:
                registros.append(HistorialPrecio(
                    producto=self, tipo='venta',
                    precio_anterior=precios_anteriores['venta'],
                    precio_nuevo=self.precio_venta,
                    cambiado_por=_usuario,
                ))
            if registros:
                HistorialPrecio.objects.bulk_create(registros)

    @property
    def stock_bajo(self):
        return self.stock_actual <= self.stock_minimo

    @property
    def dias_cobertura_efectivo(self):
        """
        Herencia de días de cobertura:
          1. Valor propio del producto (si está definido)
          2. Valor predeterminado de la categoría (si existe)
          3. Fallback global: 7 días
        """
        if self.dias_cobertura is not None:
            return self.dias_cobertura
        if self.categoria and self.categoria.dias_cobertura_default is not None:
            return self.categoria.dias_cobertura_default
        return 7

    @property
    def cantidad_sugerida_pedido(self):
        from ventas.models import DetalleVenta
        from datetime import date, timedelta
        from django.db.models import Sum
        hace_7_dias = date.today() - timedelta(days=7)
        vendido = DetalleVenta.objects.filter(
            producto=self,
            venta__fecha__gte=hace_7_dias,
            venta__estado__in=['procesada', 'a_credito', 'pagada']
        ).aggregate(total=Sum('cantidad'))['total'] or 0
        promedio_diario = vendido / 7
        necesario = (promedio_diario * self.dias_cobertura_efectivo) - self.stock_actual
        return max(int(necesario), self.stock_minimo)

    def __str__(self):
        return f"[{self.codigo or 'PEND'}] {self.nombre}"


class SolicitudInventario(models.Model):
    # Anotación de tipo para evitar que Pylance marque 'id' como desconocido
    id: int

    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('aprobada',   'Aprobada'),
        ('rechazada', 'Rechazada'),
    ]
    empleado            = models.ForeignKey(
        'core.Usuario', on_delete=models.CASCADE,
        related_name='solicitudes_enviadas'
    )
    admin               = models.ForeignKey(
        'core.Usuario', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='solicitudes_recibidas'
    )
    producto            = models.ForeignKey(Producto, on_delete=models.PROTECT)
    cantidad_solicitada = models.IntegerField()
    estado              = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='pendiente')
    observacion         = models.TextField(blank=True)
    fecha_solicitud     = models.DateTimeField(auto_now_add=True)
    fecha_respuesta     = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Solicitud #{self.id} — {self.empleado} → {self.producto}"


class HistorialPrecio(models.Model):
    """
    Registra cada cambio de precio_compra o precio_venta de un producto.
    Se inserta automáticamente en Producto.save() cuando se detecta un cambio.
    Los registros son inmutables — sólo INSERT, nunca UPDATE ni DELETE.
    """
    TIPO_CHOICES = [
        ('compra', 'Precio de compra'),
        ('venta',  'Precio de venta'),
    ]
    producto       = models.ForeignKey(
        Producto, on_delete=models.CASCADE, related_name='historial_precios'
    )
    tipo           = models.CharField(max_length=6, choices=TIPO_CHOICES)
    precio_anterior = models.DecimalField(max_digits=12, decimal_places=2)
    precio_nuevo    = models.DecimalField(max_digits=12, decimal_places=2)
    fecha           = models.DateTimeField(auto_now_add=True, db_index=True)
    cambiado_por    = models.ForeignKey(
        'core.Usuario', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='cambios_precio'
    )

    class Meta:
        ordering = ['-fecha']
        verbose_name        = 'Historial de precio'
        verbose_name_plural = 'Historial de precios'

    def __str__(self):
        return (
            f'{self.producto.nombre} — {self.get_tipo_display()}: '
            f'{self.precio_anterior} → {self.precio_nuevo}'
        )

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError('Los registros de historial de precios son inmutables.')
        super().save(*args, **kwargs)


class MovimientoInventario(models.Model):
    TIPO_CHOICES = [
        ('entrada', 'Entrada'),
        ('salida',   'Salida'),
        ('ajuste',   'Ajuste'),
    ]
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    tipo     = models.CharField(max_length=10, choices=TIPO_CHOICES)
    cantidad = models.IntegerField()
    motivo   = models.CharField(max_length=200, blank=True)
    fecha    = models.DateTimeField(auto_now_add=True)
    usuario  = models.ForeignKey('core.Usuario', on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.tipo} — {self.producto} ({self.cantidad})"