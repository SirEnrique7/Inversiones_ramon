# ══════════════════════════════════════════════════════════════
# MODELS — Módulo Core
# Reemplaza/extiende el models.py existente del proyecto
# ══════════════════════════════════════════════════════════════

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone


# ─────────────────────────────────────────────
# 1. USUARIO EXTENDIDO
# ─────────────────────────────────────────────

class Usuario(AbstractUser):
    ROL_CHOICES = [
        ('admin',      'Administrador'),
        ('encargado',  'Encargado / Almacenista'),
    ]

    rol             = models.CharField(max_length=20, choices=ROL_CHOICES, default='encargado')
    cedula          = models.CharField(max_length=15, unique=True, verbose_name='Cédula de identidad')
    telefono        = models.CharField(max_length=20, blank=True)
    # email ya existe en AbstractUser, solo lo marcamos único
    email           = models.EmailField(unique=True, verbose_name='Correo electrónico')
    fecha_ingreso   = models.DateField(default=timezone.now)
    fecha_baja      = models.DateTimeField(null=True, blank=True)
    dado_de_baja_por = models.ForeignKey(
        'self', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='bajas_ejecutadas'
    )

    # AbstractUser ya trae: first_name, last_name, is_active, is_staff, date_joined

    # ── Helpers de rol ──
    def es_admin(self):
        return self.rol == 'admin'

    def es_encargado(self):
        return self.rol == 'encargado'

    # ── Baja lógica: nunca DELETE ──
    def dar_de_baja(self, ejecutado_por):
        """
        Desactiva la cuenta sin eliminar el registro.
        Preserva toda la integridad referencial histórica.
        """
        self.is_active    = False
        self.fecha_baja   = timezone.now()
        self.dado_de_baja_por = ejecutado_por
        self.save(update_fields=['is_active', 'fecha_baja', 'dado_de_baja_por'])

    def reactivar(self, ejecutado_por):
        self.is_active        = True
        self.fecha_baja       = None
        self.dado_de_baja_por = None   # Limpiar: el campo es "quién dio de baja", no "quién reactivó"
        self.save(update_fields=['is_active', 'fecha_baja', 'dado_de_baja_por'])

    def get_nombre_completo(self):
        return f"{self.first_name} {self.last_name}".strip() or self.username

    def __str__(self):
        estado = '' if self.is_active else ' [INACTIVO]'
        return f"{self.get_nombre_completo()} ({self.get_rol_display()}){estado}"

    class Meta:
        verbose_name        = 'Usuario'
        verbose_name_plural = 'Usuarios'
        ordering            = ['last_name', 'first_name']

    # Requerido por Django cuando se usa AUTH_USER_MODEL personalizado
    USERNAME_FIELD  = 'username'
    REQUIRED_FIELDS = ['email', 'cedula', 'first_name', 'last_name']


# ─────────────────────────────────────────────
# 2. TASA DE CAMBIO BCV
# ─────────────────────────────────────────────

class TasaCambio(models.Model):
    """
    Almacena la tasa BCV extraída automáticamente una vez por día.
    Referencia estática para todas las transacciones de las siguientes 24h.
    """
    fecha       = models.DateField(unique=True, verbose_name='Fecha')
    tasa_bs_usd = models.DecimalField(
        max_digits=12, decimal_places=2,
        verbose_name='Tasa Bs./USD (BCV)'
    )
    hora_extraccion = models.DateTimeField(auto_now_add=True)
    fuente      = models.CharField(max_length=100, default='bcv.org.ve')

    @classmethod
    def tasa_hoy(cls):
        """Devuelve la tasa del día o None si aún no se ha extraído."""
        try:
            return cls.objects.get(fecha=timezone.now().date())
        except cls.DoesNotExist:
            return None

    @classmethod
    def tasa_vigente(cls):
        """Devuelve la tasa más reciente disponible (fallback seguro)."""
        return cls.objects.order_by('-fecha').first()

    def __str__(self):
        return f"{self.fecha} — Bs. {self.tasa_bs_usd} / USD"

    class Meta:
        verbose_name        = 'Tasa de cambio'
        verbose_name_plural = 'Tasas de cambio'
        ordering            = ['-fecha']


# ─────────────────────────────────────────────
# 3. AUDITORÍA / LOG DE ACCIONES
# ─────────────────────────────────────────────

class AuditoriaAccion(models.Model):
    """
    Registro inmutable de acciones críticas del sistema.
    Garantiza no repudio e integridad histórica.
    """
    ACCION_CHOICES = [
        # Usuarios
        ('login',           'Inicio de sesión'),
        ('logout',          'Cierre de sesión'),
        ('login_fallido',   'Intento de login fallido'),
        ('alta_usuario',    'Alta de usuario'),
        ('baja_usuario',    'Baja de usuario'),
        ('reactivacion_usuario', 'Reactivación de usuario'),
        ('edicion_usuario', 'Edición de usuario'),
        # Inventario
        ('crear_producto',    'Producto creado'),
        ('editar_producto',   'Producto editado'),
        ('ajuste_stock',      'Ajuste manual de stock'),
        # Compras
        ('crear_compra',    'Orden de compra creada'),
        ('aprobar_compra',  'Orden de compra aprobada'),
        ('rechazar_compra', 'Orden de compra rechazada'),
        ('cancelar_compra', 'Orden de compra cancelada'),
        ('recibir_compra',  'Recepción de mercancía registrada'),
        ('pago_proveedor',  'Pago a proveedor registrado'),
        # Ventas
        ('crear_venta',     'Venta procesada'),
        ('cancelar_venta',  'Venta cancelada'),
        ('pago_cliente',    'Pago de cliente registrado'),
        ('crear_cliente',   'Cliente registrado'),
        ('editar_cliente',  'Cliente editado'),
        # Sistema
        ('tasa_bcv',        'Tasa BCV actualizada'),
    ]

    usuario        = models.ForeignKey(
        Usuario, on_delete=models.SET_NULL,
        null=True, related_name='acciones'
    )
    accion         = models.CharField(max_length=30, choices=ACCION_CHOICES)
    descripcion    = models.TextField(blank=True)       # detalle legible
    ip_address     = models.GenericIPAddressField(null=True, blank=True)
    objeto_tipo    = models.CharField(max_length=50, blank=True)  # ej. 'Compra'
    objeto_id      = models.PositiveIntegerField(null=True, blank=True)
    fecha          = models.DateTimeField(auto_now_add=True, db_index=True)

    # El log es inmutable: no se permite update ni delete desde el ORM
    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError('Los registros de auditoría son inmutables.')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError('Los registros de auditoría no pueden eliminarse.')

    @classmethod
    def registrar(cls, usuario, accion, descripcion='', request=None, objeto_tipo='', objeto_id=None):
        ip = None
        if request:
            x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
            ip = x_forwarded.split(',')[0] if x_forwarded else request.META.get('REMOTE_ADDR')
        cls.objects.create(
            usuario=usuario,
            accion=accion,
            descripcion=descripcion,
            ip_address=ip,
            objeto_tipo=objeto_tipo,
            objeto_id=objeto_id,
        )

    def __str__(self):
        return f"{self.fecha:%d/%m/%Y %H:%M} — {self.usuario} — {self.get_accion_display()}"

    class Meta:
        verbose_name        = 'Registro de auditoría'
        verbose_name_plural = 'Registros de auditoría'
        ordering            = ['-fecha']

# Importar modelos bimonetarios para que Django los registre bajo la app 'core'
from core.models_bimonetario import (
    MontoMixin,
    Cliente,
    CuentaPorPagar,
    AbonoCuentaPagar,
    CuentaPorCobrar,
    AbonoCuentaCobrar,
)