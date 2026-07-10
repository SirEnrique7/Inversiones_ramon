from django.contrib import admin
from .models import Compra, DetalleCompra

class DetalleCompraInline(admin.TabularInline):
    model = DetalleCompra
    extra = 0  # Evita que aparezcan filas vacías molestas al final de la lista
    # RECTIFICACIÓN: Hacemos los campos calculados del detalle de solo lectura para evitar fraudes u omisiones
    readonly_fields = ['producto', 'cantidad_pedida', 'cantidad_recibida', 'precio_unitario']
    
    def has_add_permission(self, request, obj=None):
        # Las órdenes de compra se crean desde el frontend transaccional, no a mano en el admin
        return False

    def has_delete_permission(self, request, obj=None):
        # Previene la eliminación accidental de un artículo de la orden desde el admin
        return False


@admin.register(Compra)
class CompraAdmin(admin.ModelAdmin):
    # Configuración de la lista principal
    list_display = ['numero_referencia', 'proveedor', 'estado', 'modalidad_pago', 'pagado', 'mostrar_total']
    list_filter = ['estado', 'modalidad_pago', 'pagado', 'fecha_creacion']
    search_fields = ['numero_referencia', 'proveedor__nombre', 'referencia_documento']
    
    # Inyección de los productos solicitados directamente dentro de la vista de la orden
    inlines = [DetalleCompraInline]
    
    # RECTIFICACIÓN: Agregamos 'total' a los campos de solo lectura para salvaguardar la integridad contable
    readonly_fields = ['numero_referencia', 'fecha_creacion', 'total', 'creada_por']
    
    # Organización del formulario por secciones semánticas (UX Avanzada)
    fieldsets = (
        ('Identificación de la Orden', {
            'fields': ('numero_referencia', 'proveedor', 'creada_por')
        }),
        ('Estado Operativo y Financiero', {
            'fields': ('estado', 'modalidad_pago', 'pagado')
        }),
        ('Control de Fechas y Totales', {
            'fields': ('fecha_creacion', 'fecha_estimada', 'total')
        }),
    )

    @admin.display(description='Total (Bs.)')
    def mostrar_total(self, obj):
        """Formatea el total monetario directamente en la lista del panel."""
        return f"Bs. {obj.total:,.2f}"

    def save_model(self, request, obj, form, change):
        """Asigna automáticamente el usuario que audita o crea la orden si no existe."""
        if not obj.pk:
            obj.creada_por = request.user
        super().save_model(request, obj, form, change)