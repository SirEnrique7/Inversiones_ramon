from django.urls import path
from . import views

app_name = 'ventas'

urlpatterns = [
    path('',                      views.lista_ventas,      name='lista_ventas'),
    path('nueva/',                views.crear_venta,       name='crear_venta'),
    path('<int:pk>/',             views.detalle_venta,     name='detalle_venta'),
    path('<int:pk>/factura/',     views.ver_factura,       name='ver_factura'),
    path('<int:pk>/cancelar/',    views.cancelar_venta,    name='cancelar_venta'),
    path('api/stock/',            views.api_stock_producto, name='api_stock'),
]
