from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario, TasaCambio, AuditoriaAccion


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display  = ['username', 'get_nombre_completo', 'cedula', 'rol', 'is_active']
    list_filter   = ['rol', 'is_active']
    search_fields = ['username', 'cedula', 'email', 'first_name', 'last_name']
    fieldsets = UserAdmin.fieldsets + (
        ('Datos adicionales', {'fields': ('rol', 'cedula', 'telefono', 'fecha_ingreso')}),
    )


@admin.register(TasaCambio)
class TasaCambioAdmin(admin.ModelAdmin):
    list_display = ['fecha', 'tasa_bs_usd', 'hora_extraccion']
    ordering     = ['-fecha']


@admin.register(AuditoriaAccion)
class AuditoriaAdmin(admin.ModelAdmin):
    list_display    = ['fecha', 'usuario', 'accion', 'ip_address']
    list_filter     = ['accion']
    readonly_fields = ['fecha', 'usuario', 'accion', 'descripcion',
                       'ip_address', 'objeto_tipo', 'objeto_id']
    def has_add_permission(self, request):    return False
    def has_delete_permission(self, request, obj=None): return False
