# ══════════════════════════════════════════════════════════════
# signals.py — Módulo Compras
#
# Las señales de sincronización de totales (post_save / post_delete
# de DetalleCompra) están registradas directamente en models.py
# mediante @receiver para mantener todo en un solo lugar.
#
# La actualización de stock al recibir una orden se hace de forma
# explícita en recibir_compra (views.py) dentro de transaction.atomic(),
# lo que garantiza rollback si algo falla — un signal no puede hacer eso.
# ══════════════════════════════════════════════════════════════
