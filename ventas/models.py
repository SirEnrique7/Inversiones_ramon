# ══════════════════════════════════════════════════════════════
# MODELS — Módulo Ventas (Optimizado para Pylance)
# ══════════════════════════════════════════════════════════════

from django.db import models
from django.utils import timezone
from decimal import Decimal


class Venta(models.Model):

    ESTADO_CHOICES = [
        ('procesada', 'Procesada'),
        ('a_credito', 'A crédito / Fiado'),
        ('pagada',    'Pagada'),
        ('cancelada', 'Cancelada'),
    ]

    METODO_CHOICES = [
        ('punto',      'Punto de venta'),
        ('pago_movil', 'Pago móvil'),
        ('biopago',    'BioPago'),
        ('mixto',      'Mixto'),
        ('credito',    'A crédito / Fiado'),
    ]

    # ── Quién y cuándo ──
    empleado       = models.ForeignKey(
        'core.Usuario', on_delete=models.SET_NULL, null=True,
        related_name='ventas'
    )
    fecha          = models.DateField(auto_now_add=True)
    hora           = models.TimeField(auto_now_add=True)

    # ── Cliente (obligatorio para crédito) ──
    cliente        = models.ForeignKey(
        'core.Cliente', on_delete=models.PROTECT,
        null=True, blank=True, related_name='ventas'
    )

    # ── Pago ──
    metodo_pago    = models.CharField(max_length=15, choices=METODO_CHOICES)
    referencia_pago = models.CharField(
        max_length=100, blank=True,
        verbose_name='Referencia de pago'
    )
    estado         = models.CharField(
        max_length=15, choices=ESTADO_CHOICES, default='procesada'
    )
    fecha_estimada_pago = models.DateField(
        null=True, blank=True,
        verbose_name='Fecha estimada de pago (crédito)'
    )

    # ── Montos (Cambiados a Decimal explícito para evitar que Pylance proteste) ──
    subtotal_bs    = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    iva_bs         = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    total_bs       = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    tasa_bcv_momento = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    total_usd      = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )

    # ── Número de factura ──
    numero_factura = models.CharField(
        max_length=20, unique=True, blank=True, null=True,
        verbose_name='Número de factura'
    )

    # ── Auditoría ──
    observacion    = models.TextField(blank=True)

    # ─────────────────────────────────────────
    def save(self, *args, **kwargs):
        if self.metodo_pago == 'credito' and not self.cliente:
            raise ValueError("Error: No se puede procesar una venta a crédito sin registrar un Cliente.")

        if self.metodo_pago == 'credito' and self.estado == 'procesada':
            self.estado = 'a_credito'

        # En inserciones nuevas sin factura, guardamos NULL para que el
        # UNIQUE de PostgreSQL no colisione mientras el pk no está asignado.
        if self._state.adding and not self.numero_factura:
            self.numero_factura = None

        super().save(*args, **kwargs)

        if not self.numero_factura:
            self.numero_factura = f"FAC-{self.pk:06d}"
            Venta.objects.filter(pk=self.pk).update(
                numero_factura=self.numero_factura
            )

    def calcular_totales(self, porcentaje_iva=16):
        """Calcula IVA y total. Fija conversión USD si hay tasa."""
        self.iva_bs   = (self.subtotal_bs * Decimal(str(porcentaje_iva)) / 100).quantize(Decimal('0.01'))
        self.total_bs = self.subtotal_bs + self.iva_bs

        if self.tasa_bcv_momento and self.tasa_bcv_momento > 0:
            self.total_usd = (
                self.total_bs / self.tasa_bcv_momento
            ).quantize(Decimal('0.01'))

        self.save(update_fields=[
            'subtotal_bs', 'iva_bs', 'total_bs', 'tasa_bcv_momento', 'total_usd',
        ])

    def es_credito(self):
        return self.metodo_pago == 'credito'

    def __str__(self):
        # Usamosgetattr para silenciar el falso positivo de Pylance con los métodos mágicos de Django
        estado_display = getattr(self, 'get_estado_display', lambda: self.estado)()
        return f"{self.numero_factura or 'PEND'} — {self.fecha} ({estado_display})"

    class Meta:
        verbose_name        = 'Venta'
        verbose_name_plural = 'Ventas'
        ordering            = ['-fecha', '-hora']


# ─────────────────────────────────────────
class DetalleVenta(models.Model):
    venta           = models.ForeignKey(
        Venta, on_delete=models.CASCADE, related_name='detalles'
    )
    producto        = models.ForeignKey(
        'inventario.Producto', on_delete=models.PROTECT
    )
    cantidad        = models.IntegerField()
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2)
    subtotal        = models.DecimalField(
        max_digits=14, decimal_places=2, editable=False, default=Decimal('0.00')
    )

    def save(self, *args, **kwargs):
        self.subtotal = self.cantidad * self.precio_unitario
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.producto.nombre} x{self.cantidad}"

    class Meta:
        verbose_name = 'Detalle de venta'