from django.urls import path
from . import views, api

app_name = 'inventario'

urlpatterns = [
    # DASHBOARD
    path('', views.dashboard, name='dashboard'),
    
    # PRODUCTOS
    path('productos/', views.lista_productos, name='lista_productos'),
    path('productos/nuevo/', views.crear_producto, name='crear_producto'),
    path('productos/<int:pk>/', views.detalle_producto, name='detalle_producto'),
    path('productos/<int:pk>/editar/', views.editar_producto, name='editar_producto'),
    path('productos/<int:pk>/desactivar/', views.desactivar_producto, name='desactivar_producto'),
    
    # CATEGORÍAS
    path('categorias/', views.lista_categorias, name='lista_categorias'),
    path('categorias/nueva/', views.crear_categoria, name='crear_categoria'),
    path('categorias/<int:pk>/editar/', views.editar_categoria, name='editar_categoria'),
    
    # PROVEEDORES
    path('proveedores/', views.lista_proveedores, name='lista_proveedores'),
    path('proveedores/nuevo/', views.crear_proveedor, name='crear_proveedor'),
    path('proveedores/<int:pk>/editar/', views.editar_proveedor, name='editar_proveedor'),
    
    # SOLICITUDES DE INVENTARIO
    path('solicitudes/', views.lista_solicitudes, name='lista_solicitudes'),
    path('solicitudes/nueva/', views.crear_solicitud, name='crear_solicitud'),
    path('solicitudes/<int:pk>/responder/', views.responder_solicitud, name='responder_solicitud'),
    
    # ENDPOINTS ASÍNCRONOS (APIs)
    path('api/sugerencia/', api.api_sugerencia_cantidad, name='api_sugerencia'),
    path('api/producto/',   api.api_producto_info,       name='api_producto'),
]