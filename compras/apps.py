from django.apps import AppConfig

class ComprasConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'compras'
    verbose_name = 'Gestión de Compras y Abastecimiento'
    # Las señales post_save / post_delete de DetalleCompra están registradas
    # directamente en compras/models.py con @receiver, por lo que Django las
    # activa en cuanto importa el modelo. No se necesita ready() aquí.