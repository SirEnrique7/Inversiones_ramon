# ══════════════════════════════════════════════════════════════
# core/excel_utils.py
# Utilidad compartida para exportar listados a Excel (.xlsx real).
#
# Usada por compras, ventas e inventario para no triplicar la misma
# lógica de estilos/formato en cada módulo. Reemplaza la exportación
# a CSV que existía antes en los tres lugares.
# ══════════════════════════════════════════════════════════════
from decimal import Decimal

from django.http import HttpResponse
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


def exportar_excel(nombre_hoja, headers, filas, filename):
    """
    Genera y devuelve un HttpResponse con un archivo .xlsx listo para
    descargar, con encabezado en negrita, columnas ajustadas al
    contenido y la primera fila congelada.

    nombre_hoja : título de la pestaña (Excel limita a 31 caracteres,
                  se recorta automáticamente si hace falta).
    headers     : lista con los nombres de columna.
    filas       : lista de listas/tuplas con los valores de cada fila,
                  en el mismo orden que 'headers'.
    filename    : nombre del archivo a descargar, ej. 'compras.xlsx'.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = (nombre_hoja or 'Datos')[:31]

    ws.append(list(headers))

    header_font  = Font(bold=True, color='FFFFFF')
    header_fill  = PatternFill(start_color='1A56DB', end_color='1A56DB', fill_type='solid')
    header_align = Alignment(horizontal='center', vertical='center')
    for cell in ws[1]:
        cell.font      = header_font
        cell.fill      = header_fill
        cell.alignment = header_align

    for fila in filas:
        fila_limpia = []
        for valor in fila:
            if valor is None:
                fila_limpia.append('')
            elif isinstance(valor, Decimal):
                # Excel guarda todo como float de punto flotante de todos
                # modos; convertimos explícito para evitar cualquier
                # incompatibilidad de tipo entre versiones de openpyxl.
                fila_limpia.append(float(valor))
            else:
                fila_limpia.append(valor)
        ws.append(fila_limpia)

    # Autoajustar ancho de columnas según el contenido más largo
    for col_cells in ws.columns:
        col_letter = get_column_letter(col_cells[0].column)
        max_len = max(
            (len(str(c.value)) for c in col_cells if c.value is not None),
            default=8
        )
        ws.column_dimensions[col_letter].width = min(max_len + 3, 45)

    ws.freeze_panes = 'A2'  # La fila de encabezado queda fija al hacer scroll

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response
