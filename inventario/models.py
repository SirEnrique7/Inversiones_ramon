from django.db import models

class Categoria(models.Model):
    nombre      = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)

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
    dias_cobertura = models.IntegerField(default=7)
    categoria      = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True)
    proveedor      = models.ForeignKey(Proveedor, on_delete=models.SET_NULL, null=True)
    activo         = models.BooleanField(default=True)
    en_tendencia   = models.BooleanField(
        default=False,
        verbose_name='En tendencia',
        help_text='Actualizado por el motor de reportes automáticamente.'
    )

    def save(self, *args, **kwargs):
        # En inserciones nuevas sin código, guardamos NULL para que el
        # UNIQUE de PostgreSQL no colisione mientras el pk no está asignado.
        if self._state.adding and not self.codigo:
            self.codigo = None
        super().save(*args, **kwargs)
        if not self.codigo:
            self.codigo = f"PROD-{self.id:04d}"
            Producto.objects.filter(pk=self.pk).update(codigo=self.codigo)

    @property
    def stock_bajo(self):
        return self.stock_actual <= self.stock_minimo

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
        necesario = (promedio_diario * self.dias_cobertura) - self.stock_actual
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