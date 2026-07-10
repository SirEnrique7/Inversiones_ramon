from typing import TYPE_CHECKING
from django.db import models, transaction
from django.utils import timezone
from decimal import Decimal

class MontoMixin(models.Model):
    monto_bs = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    tasa_bcv_momento = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    monto_usd = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    def fijar_conversion(self, monto_bs, tasa):
        self.monto_bs = monto_bs
        self.tasa_bcv_momento = tasa
        if tasa and tasa > 0:
            self.monto_usd = (monto_bs / Decimal(str(tasa))).quantize(Decimal('0.01'))
        else:
            self.monto_usd = None

    class Meta:
        abstract = True


class Cliente(models.Model):
    cedula_rif = models.CharField(max_length=20, unique=True, verbose_name='Cédula / RIF')
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100, blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    direccion = models.TextField(blank=True)
    fecha_registro = models.DateField(auto_now_add=True)

    def get_nombre_completo(self):
        return f"{self.nombre} {self.apellido}".strip()

    def __str__(self):
        return f"{self.get_nombre_completo()} ({self.cedula_rif})"

    class Meta:
        ordering = ['apellido', 'nombre']
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'


class CuentaPorPagar(MontoMixin):
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('abonada', 'Abonada parcialmente'),
        ('saldada', 'Saldada'),
    ]

    # Indicación explícita para que el editor reconozca la relación inversa sin alterar Django
    if TYPE_CHECKING:
        abonos: models.Manager['AbonoCuentaPagar']

    proveedor = models.ForeignKey(
        'inventario.Proveedor', on_delete=models.PROTECT,
        related_name='cuentas_por_pagar'
    )
    compra = models.OneToOneField(
        'compras.Compra', on_delete=models.PROTECT,
        related_name='cuenta_por_pagar'
    )
    saldo_restante = models.DecimalField(max_digits=14, decimal_places=2)
    estado = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='pendiente')
    fecha_generacion = models.DateTimeField(auto_now_add=True)
    fecha_vencimiento = models.DateField(null=True, blank=True)
    fecha_saldada = models.DateTimeField(null=True, blank=True)
    registrada_por = models.ForeignKey(
        'core.Usuario', on_delete=models.SET_NULL, null=True,
        related_name='cuentas_pagar_registradas'
    )

    def registrar_abono(self, monto_abono, referencia, usuario, tasa_bcv):
        with transaction.atomic():
            if monto_abono <= 0:
                raise ValueError('El monto debe ser mayor a cero.')
            if monto_abono > self.saldo_restante:
                raise ValueError('El abono supera el saldo restante.')
            
            AbonoCuentaPagar.objects.create(
                cuenta=self, monto_bs=monto_abono, tasa_bcv=tasa_bcv,
                referencia=referencia, registrado_por=usuario,
            )
            self.saldo_restante -= monto_abono
            if self.saldo_restante <= Decimal('0.00'):
                self.saldo_restante = Decimal('0.00')
                self.estado = 'saldada'
                self.fecha_saldada = timezone.now()
                self.compra.pagado = True
                self.compra.save(update_fields=['pagado'])
            else:
                self.estado = 'abonada'
            self.save(update_fields=['saldo_restante', 'estado', 'fecha_saldada'])

    @property
    def vencida(self):
        from datetime import date
        return (self.estado != 'saldada' and self.fecha_vencimiento
                and self.fecha_vencimiento < date.today())

    def __str__(self):
        return f"CPP-{self.pk:04d} | {self.proveedor} | Bs. {self.saldo_restante}"

    # Al heredar de MontoMixin.Meta, Pylance valida la sobrescritura correctamente
    class Meta(MontoMixin.Meta):
        ordering = ['estado', 'fecha_vencimiento']
        verbose_name = 'Cuenta por pagar'
        verbose_name_plural = 'Cuentas por pagar'


class AbonoCuentaPagar(models.Model):
    cuenta = models.ForeignKey(CuentaPorPagar, on_delete=models.CASCADE, related_name='abonos')
    monto_bs = models.DecimalField(max_digits=14, decimal_places=2)
    tasa_bcv = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('1.00'))
    referencia = models.CharField(max_length=100)
    fecha = models.DateTimeField(auto_now_add=True)
    registrado_por = models.ForeignKey('core.Usuario', on_delete=models.SET_NULL, null=True)

    class Meta:
        ordering = ['-fecha']


class CuentaPorCobrar(MontoMixin):
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('abonada', 'Abonada parcialmente'),
        ('saldada', 'Saldada'),
    ]

    # Indicación explícita para que el editor reconozca la relación inversa sin alterar Django
    if TYPE_CHECKING:
        abonos: models.Manager['AbonoCuentaCobrar']

    venta = models.OneToOneField(
        'ventas.Venta', on_delete=models.PROTECT,
        related_name='cuenta_por_cobrar'
    )
    cliente = models.ForeignKey(
        Cliente, on_delete=models.PROTECT,
        related_name='cuentas_por_cobrar'
    )
    saldo_restante = models.DecimalField(max_digits=14, decimal_places=2)
    estado = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='pendiente')
    fecha_venta = models.DateField()
    fecha_estimada_pago = models.DateField()
    fecha_real_pago = models.DateTimeField(null=True, blank=True)
    registrada_por = models.ForeignKey(
        'core.Usuario', on_delete=models.SET_NULL, null=True,
        related_name='cuentas_cobrar_registradas'
    )

    def registrar_pago(self, monto_pago, referencia, usuario, tasa_bcv):
        with transaction.atomic():
            if monto_pago <= 0:
                raise ValueError('El monto debe ser mayor a cero.')
            if monto_pago > self.saldo_restante:
                raise ValueError('El pago supera el saldo restante.')
            
            AbonoCuentaCobrar.objects.create(
                cuenta=self, monto_bs=monto_pago, tasa_bcv=tasa_bcv,
                referencia=referencia, registrado_por=usuario,
            )
            self.saldo_restante -= monto_pago
            if self.saldo_restante <= Decimal('0.00'):
                self.saldo_restante = Decimal('0.00')
                self.estado = 'saldada'
                self.fecha_real_pago = timezone.now()
                self.venta.estado = 'pagada'
                self.venta.save(update_fields=['estado'])
            else:
                self.estado = 'abonada'
            self.save(update_fields=['saldo_restante', 'estado', 'fecha_real_pago'])

    @property
    def vencida(self):
        from datetime import date
        return (self.estado != 'saldada'
                and self.fecha_estimada_pago < date.today())

    def __str__(self):
        return f"CPC-{self.pk:04d} | {self.cliente} | Bs. {self.saldo_restante}"

    # Al heredar de MontoMixin.Meta, Pylance valida la sobrescritura correctamente
    class Meta(MontoMixin.Meta):
        ordering = ['estado', 'fecha_estimada_pago']
        verbose_name = 'Cuenta por cobrar'
        verbose_name_plural = 'Cuentas por cobrar'


class AbonoCuentaCobrar(models.Model):
    cuenta = models.ForeignKey(CuentaPorCobrar, on_delete=models.CASCADE, related_name='abonos')
    monto_bs = models.DecimalField(max_digits=14, decimal_places=2)
    tasa_bcv = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('1.00'))
    referencia = models.CharField(max_length=100)
    fecha = models.DateTimeField(auto_now_add=True)
    registrado_por = models.ForeignKey('core.Usuario', on_delete=models.SET_NULL, null=True)

    class Meta:
        ordering = ['-fecha']