from django.urls import path
from . import views

app_name = 'compras'

urlpatterns = [
    path('',                          views.lista_compras,   name='lista_compras'),
    path('nueva/',                    views.crear_compra,    name='crear_compra'),
    path('<int:pk>/',                 views.detalle_compra,  name='detalle_compra'),
    path('<int:pk>/aprobar/',         views.aprobar_compra,  name='aprobar_compra'),
    path('<int:pk>/recibir/',         views.recibir_compra,  name='recibir_compra'),
    path('<int:pk>/cancelar/',        views.cancelar_compra, name='cancelar_compra'),
]
