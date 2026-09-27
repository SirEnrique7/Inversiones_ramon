# ══════════════════════════════════════════════════════════════
# MODELS — Módulo Compras (Versión Definitiva Sin Alertas)
# ══════════════════════════════════════════════════════════════

from django.db import models
from django.utils import timezone
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from decimal import Decimal
from typing import Any


class Compra(models.Model):
    ESTADO_CHOICES = [
        ('pendiente',  'Pendiente de aprobación'),
        ('aprobada',   'Aprobada'),
        ('recibida',   'Recibida'),
        ('rechazada',  'Rechazada'),
        ('cancelada',  'Cancelada'),
    ]
    PAGO_CHOICES = [
        ('contado', 'Contado'),
        ('credito', 'Crédito'),
    ]

    creada_por           = models.ForeignKey('core.Usuario', on_delete=models.SET_NULL,
                                             null=True, related_name='compras_creadas')
    aprobada_por         = models.ForeignKey('core.Usuario', on_delete=models.SET_NULL,
                                             null=True, blank=True, related_name='compras_aprobadas')
    proveedor            = models.ForeignKey('inventario.Proveedor', on_delete=models.PROTECT,
                                             related_name='compras')
    # db_index=True: filtrada en el reporte de compras por rango de fechas.
    fecha_creacion       = models.DateTimeField(auto_now_add=True, db_index=True)
    fecha_aprobacion     = models.DateTimeField(null=True, blank=True)
    fecha_estimada       = models.DateField(null=True, blank=True,
                                             verbose_name='Fecha estimada de entrega')
    fecha_recepcion      = models.DateTimeField(null=True, blank=True,
                                               verbose_name='Fecha real de recepción')
    estado               = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='pendiente')
    modalidad_pago       = models.CharField(max_length=10, choices=PAGO_CHOICES,
                                             null=True, blank=True)
    pagado               = models.BooleanField(default=False)
    fecha_vencimiento    = models.DateField(null=True, blank=True,
                                             verbose_name='Fecha límite de pago')
    
    referencia_documento = models.CharField(max_length=100, blank=True,
                                             verbose_name='Referencia / Nro. documento')
    numero_referencia    = models.CharField(max_length=30, unique=True, blank=True, null=True,
                                             verbose_name='Referencia interna')
    observacion          = models.TextField(blank=True)
    motivo_rechazo       = models.TextField(blank=True)
    total                = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))

    def save(self, *args, **kwargs):
        # Para actualizaciones donde ya existe el ID, asignamos referencia antes del save
        compra_id = getattr(self, 'id', None)
        if not self.numero_referencia and compra_id:
            self.numero_referencia = f"OC-{compra_id:05d}"

        # En inserciones nuevas sin referencia, guardamos NULL para que el
        # UNIQUE de PostgreSQL no colisione mientras el pk no está asignado.
        if self._state.adding and not self.numero_referencia:
            self.numero_referencia = None

        super().save(*args, **kwargs)

        # Si fue la primera inserción, generamos la OC con el ID real asignado por la BD
        if not self.numero_referencia:
            nuevo_id = getattr(self, 'id', 0)
            self.numero_referencia = f"OC-{nuevo_id:05d}"
            # Update directo para no disparar señales recursivas
            Compra.objects.filter(pk=self.pk).update(numero_referencia=self.numero_referencia)

    def calcular_total(self):
        from django.db.models import Sum
        detalles_rel = getattr(self, 'detalles', None)
        if detalles_rel:
            resultado = detalles_rel.aggregate(t=Sum('subtotal'))['t']
            self.total = resultado or Decimal('0.00')
        else:
            self.total = Decimal('0.00')
        
        # Evitamos ejecutar todo el save() complejo usando update_fields
        self.save(update_fields=['total'])

    def puede_aprobar(self, usuario: Any) -> bool:
        return usuario.es_admin() and self.estado == 'pendiente'

    def puede_recibir(self, usuario: Any) -> bool:
        return (usuario.es_admin() or usuario.es_encargado()) and self.estado == 'aprobada'

    def puede_cancelar(self, usuario: Any) -> bool:
        return self.estado in ['pendiente'] and (
            usuario.es_admin() or self.creada_por == usuario
        )

    @property
    def credito_vencido(self) -> bool:
        from datetime import date
        return (self.modalidad_pago == 'credito' and not self.pagado
                and self.fecha_vencimiento is not None
                and self.fecha_vencimiento < date.today())

    def get_modalidad_pago_display(self) -> str:
        val = self.modalidad_pago or ''
        return dict(self.PAGO_CHOICES).get(val, '—')

    def __str__(self) -> str:
        estado_display = getattr(self, 'get_estado_display', lambda: self.estado)()
        return f"{self.numero_referencia or 'PEND'} — {self.proveedor} ({estado_display})"

    class Meta:
        ordering     = ['-fecha_creacion']
        verbose_name = 'Orden de compra'


# ─────────────────────────────────────────
class DetalleCompra(models.Model):
    compra            = models.ForeignKey(Compra, on_delete=models.CASCADE, related_name='detalles')
    producto          = models.ForeignKey('inventario.Producto', on_delete=models.PROTECT)
    cantidad_pedida   = models.IntegerField()
    cantidad_recibida = models.IntegerField(default=0)
    precio_unitario   = models.DecimalField(max_digits=12, decimal_places=2)
    subtotal          = models.DecimalField(max_digits=14, decimal_places=2, editable=False, default=Decimal('0.00'))

    @property
    def entrega_incompleta(self) -> bool:
        return self.cantidad_recibida < self.cantidad_pedida

    @property
    def diferencia(self) -> int:
        return self.cantidad_pedida - self.cantidad_recibida

    def save(self, *args, **kwargs):
        # El subtotal de la orden siempre se calcula con la cantidad solicitada
        cant_a_calcular = int(self.cantidad_pedida)
        
        # Tipado explícito para cálculos financieros estrictos
        self.subtotal = Decimal(cant_a_calcular) * Decimal(str(self.precio_unitario))
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.producto.nombre} — pedido:{self.cantidad_pedida}/recibido:{self.cantidad_recibida}"


# ══════════════════════════════════════════════════════════════
# SEÑALES DE INTEGRIDAD DE LA BASE DE DATOS
# ══════════════════════════════════════════════════════════════

@receiver(post_save, sender=DetalleCompra)
@receiver(post_delete, sender=DetalleCompra)
def actualizar_total_compra(sender, instance, **kwargs):
    """
    Sincronización automática de totales:
    Garantiza que el total de la compra se actualice automáticamente
    si un producto es agregado, modificado o eliminado de la orden.
    """
    if instance.compra:
        instance.compra.calcular_total()