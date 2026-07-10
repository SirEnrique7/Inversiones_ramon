from django.contrib import admin
from .models import Venta, DetalleVenta

@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display    = ['numero_factura', 'fecha', 'empleado', 'metodo_pago', 'total_bs', 'estado']
    list_filter     = ['estado', 'metodo_pago']
    search_fields   = ['numero_factura', 'cliente__nombre']
    readonly_fields = ['numero_factura', 'fecha', 'hora']
