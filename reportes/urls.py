from django.urls import path
from . import views

app_name = 'reportes'

urlpatterns = [
    path('',               views.index,          name='index'),
    path('tendencias/',    views.tendencias,      name='tendencias'),
    path('abastecimiento/', views.abastecimiento, name='abastecimiento'),
    path('ventas/',        views.rep_ventas,      name='ventas'),
    path('compras/',       views.rep_compras,     name='compras'),
    path('inventario/',    views.rep_inventario,  name='inventario'),
    path('financiero/',    views.rep_financiero,  name='financiero'),
]
