from django.contrib import admin
from django.utils import timezone
from .models import Producto, Categoria, Proveedor, MovimientoInventario, SolicitudInventario

@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display  = ['codigo', 'nombre', 'categoria', 'stock_actual', 'stock_minimo', 'en_tendencia', 'activo']
    list_filter   = ['categoria', 'activo', 'en_tendencia']
    search_fields = ['nombre', 'codigo']

@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'descripcion']

@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display  = ['nombre', 'rif', 'dia_visita', 'telefono']
    search_fields = ['nombre', 'rif']

@admin.register(MovimientoInventario)
class MovimientoAdmin(admin.ModelAdmin):
    list_display    = ['fecha', 'producto', 'tipo', 'cantidad', 'usuario']
    list_filter     = ['tipo']
    readonly_fields = ['fecha']

@admin.register(SolicitudInventario)
class SolicitudAdmin(admin.ModelAdmin):
    list_display = ['id', 'empleado', 'producto', 'cantidad_solicitada', 'estado', 'fecha_solicitud']
    list_filter  = ['estado']

    def save_model(self, request, obj, form, change):
        """Garantiza que los cambios de estado en el panel admin afecten al inventario real."""
        if change:  # Si es una edición y no una creación nueva
            original = SolicitudInventario.objects.get(pk=obj.pk)
            
            # Si el administrador aprueba la solicitud directamente desde el panel
            if original.estado == 'pendiente' and obj.estado == 'aprobada':
                producto = obj.producto
                producto.stock_actual += obj.cantidad_solicitada
                producto.save()
                
                obj.admin = request.user
                obj.fecha_respuesta = timezone.now()
                
                username_admin = getattr(request.user, 'username', 'Administrador')
                
                # Se genera el movimiento histórico correspondiente
                MovimientoInventario.objects.create(
                    producto=producto,
                    tipo='entrada',
                    cantidad=obj.cantidad_solicitada,
                    motivo=f'Solicitud #{obj.id} aprobada desde el Panel de Administración por {username_admin}',
                    usuario=request.user,
                )
                
            # Si el administrador la rechaza directamente desde el panel
            elif original.estado == 'pendiente' and obj.estado == 'rechazada':
                obj.admin = request.user
                obj.fecha_respuesta = timezone.now()

        super().save_model(request, obj, form, change)