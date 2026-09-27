# ══════════════════════════════════════════════════════════════
# core/excel_export.py
# Utilidades centralizadas para exportación a Excel (.xlsx)
# Todos los módulos del sistema usan estas funciones para
# garantizar un formato profesional y consistente.
# ══════════════════════════════════════════════════════════════

import io
from datetime import date, datetime
from decimal import Decimal

from django.http import HttpResponse
from openpyxl import Workbook
from openpyxl.styles import (
    Font, PatternFill, Alignment, Border, Side, GradientFill
)
from openpyxl.utils import get_column_letter


# ── Paleta corporativa Inversiones Ramón ──────────────────────
COLOR_HEADER_BG   = '1B3A6B'   # Azul marino oscuro (fondo encabezados)
COLOR_HEADER_FG   = 'FFFFFF'   # Blanco (texto encabezados)
COLOR_SUBHEADER   = '2D6DB5'   # Azul medio (sub-encabezados)
COLOR_TITLE_FG    = '1B3A6B'   # Azul marino (título)
COLOR_ACCENT      = 'E8F0FB'   # Azul muy claro (filas alternas)
COLOR_WHITE       = 'FFFFFF'
COLOR_TOTAL_BG    = 'D6E4F7'   # Azul pálido (fila de totales)
COLOR_TOTAL_FG    = '0D2B5E'   # Azul oscuro (texto totales)
COLOR_BORDER      = 'BFD0E8'   # Borde suave
COLOR_POSITIVO    = '1A6B3A'   # Verde (valores positivos / OK)
COLOR_NEGATIVO    = 'A61C1C'   # Rojo (valores negativos / alerta)
COLOR_NEUTRO      = '7A5C00'   # Ámbar (advertencias)

# ── Fuente base ────────────────────────────────────────────────
FONT_FAMILY = 'Arial'


def _border(color=COLOR_BORDER, style='thin'):
    """Devuelve un objeto Border uniforme en los 4 lados."""
    s = Side(style=style, color=color)
    return Border(left=s, right=s, top=s, bottom=s)


def _fill(hex_color):
    """Devuelve PatternFill sólido."""
    return PatternFill('solid', start_color=hex_color, fgColor=hex_color)


def _font(bold=False, size=10, color='000000', italic=False):
    return Font(name=FONT_FAMILY, bold=bold, size=size, color=color, italic=italic)


def _align(h='left', v='center', wrap=False):
    return Alignment(horizontal=h, vertical=v, wrap_text=wrap)


def nueva_respuesta_excel(nombre_archivo: str) -> HttpResponse:
    """
    Devuelve un HttpResponse configurado para descarga de Excel.
    nombre_archivo debe incluir la extensión .xlsx.
    """
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    return response


class ExcelExporter:
    """
    Generador de archivos Excel (.xlsx) con formato profesional.

    Uso típico:
        exp = ExcelExporter('Reporte de Ventas', 'Inversiones Ramón')
        ws  = exp.crear_hoja('Ventas', headers=[...], col_widths=[...])
        exp.escribir_fila_datos(ws, 2, [...])
        exp.escribir_fila_totales(ws, n, [...])
        exp.guardar_en_response(response)
    """

    def __init__(self, titulo: str, empresa: str = 'Inversiones Ramón'):
        self.wb     = Workbook()
        self.titulo = titulo
        self.empresa = empresa
        # Eliminar hoja por defecto (la crearemos con nombre propio)
        if 'Sheet' in self.wb.sheetnames:
            del self.wb['Sheet']

    # ── Creación de hoja ───────────────────────────────────────

    def crear_hoja(
        self,
        nombre: str,
        headers: list,
        col_widths: list = None,
        subtitulo: str = '',
        freeze_row: int = 4,
    ):
        """
        Crea una nueva hoja con:
          - Fila 1: Título del reporte (combinada)
          - Fila 2: Empresa + fecha de generación
          - Fila 3: Vacía (separador visual)
          - Fila 4 (header_row): Encabezados de columnas
          - Freeze desde fila freeze_row+1
        Retorna la hoja creada.
        """
        ws = self.wb.create_sheet(title=nombre[:31])  # Excel max 31 chars
        ncols = len(headers)

        # ── Fila 1: Título ─────────────────────────────────────
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncols)
        c = ws.cell(row=1, column=1, value=self.titulo)
        c.font      = _font(bold=True, size=14, color=COLOR_TITLE_FG)
        c.alignment = _align(h='center', v='center')
        c.fill      = _fill('EBF2FD')
        ws.row_dimensions[1].height = 22

        # ── Fila 2: Empresa + fecha ────────────────────────────
        texto_meta = f'{self.empresa}   |   Generado: {datetime.now().strftime("%d/%m/%Y %H:%M")}'
        if subtitulo:
            texto_meta = f'{subtitulo}   |   {texto_meta}'
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncols)
        c = ws.cell(row=2, column=1, value=texto_meta)
        c.font      = _font(size=9, color='555555', italic=True)
        c.alignment = _align(h='center', v='center')
        c.fill      = _fill('F5F9FF')
        ws.row_dimensions[2].height = 16

        # ── Fila 3: Separador ──────────────────────────────────
        ws.row_dimensions[3].height = 6

        # ── Fila 4: Encabezados ────────────────────────────────
        HEADER_ROW = 4
        for ci, header in enumerate(headers, 1):
            c = ws.cell(row=HEADER_ROW, column=ci, value=header)
            c.font      = _font(bold=True, size=10, color=COLOR_HEADER_FG)
            c.fill      = _fill(COLOR_HEADER_BG)
            c.alignment = _align(h='center', v='center')
            c.border    = _border(COLOR_HEADER_BG)
        ws.row_dimensions[HEADER_ROW].height = 18

        # ── Anchos de columnas ─────────────────────────────────
        if col_widths:
            for ci, w in enumerate(col_widths, 1):
                ws.column_dimensions[get_column_letter(ci)].width = w
        else:
            # Auto-anchos basados en longitud de header + padding
            for ci, h in enumerate(headers, 1):
                ws.column_dimensions[get_column_letter(ci)].width = max(len(str(h)) + 4, 12)

        # ── Freeze panes ──────────────────────────────────────
        ws.freeze_panes = ws.cell(row=freeze_row + 1, column=1)

        return ws

    # ── Escritura de datos ────────────────────────────────────

    def escribir_fila_datos(
        self,
        ws,
        row: int,
        valores: list,
        formato_moneda: list = None,
        formato_fecha: list = None,
        color_condicional: dict = None,
    ):
        """
        Escribe una fila de datos con alternancia de color (zebra).
          formato_moneda: lista de índices (0-based) de columnas con formato monetario
          formato_fecha:  lista de índices (0-based) de columnas con fecha
          color_condicional: {col_idx: (valor_comparar, color_si_true, color_si_false)}
        """
        es_par     = (row % 2 == 0)
        bg_color   = COLOR_ACCENT if es_par else COLOR_WHITE
        row_border = _border()

        fmt_moneda = set(formato_moneda or [])
        fmt_fecha  = set(formato_fecha  or [])

        for ci, val in enumerate(valores, 1):
            c         = ws.cell(row=row, column=ci)
            c.border  = row_border
            c.fill    = _fill(bg_color)

            col_idx = ci - 1  # 0-based para comparar con listas

            # Convertir Decimal a float para evitar TypeError en openpyxl
            if isinstance(val, Decimal):
                val = float(val)

            c.value = val

            if col_idx in fmt_moneda and val is not None and val != '':
                c.number_format = '#,##0.00'
                c.alignment     = _align(h='right')
                c.font          = _font(size=10)
            elif col_idx in fmt_fecha:
                c.alignment = _align(h='center')
                c.font      = _font(size=10)
            elif isinstance(val, (int, float)) and col_idx not in fmt_fecha:
                c.alignment = _align(h='right')
                c.font      = _font(size=10)
            else:
                c.alignment = _align(h='left')
                c.font      = _font(size=10)

            # Color condicional por columna
            if color_condicional and col_idx in color_condicional:
                umbral, col_verdad, col_falso = color_condicional[col_idx]
                color_texto = col_verdad if (val == umbral) else col_falso
                c.font = _font(size=10, color=color_texto)

        ws.row_dimensions[row].height = 15

    def escribir_fila_totales(self, ws, row: int, valores: list, label_col: int = 0):
        """
        Escribe la fila de totales con estilo destacado.
        label_col: índice 0-based de la columna que contiene la etiqueta "TOTAL".
        """
        for ci, val in enumerate(valores, 1):
            c        = ws.cell(row=row, column=ci)
            c.border = _border(COLOR_TOTAL_FG, style='medium')
            c.fill   = _fill(COLOR_TOTAL_BG)
            if isinstance(val, Decimal):
                val = float(val)
            c.value = val

            col_idx = ci - 1
            if col_idx == label_col:
                c.font      = _font(bold=True, size=10, color=COLOR_TOTAL_FG)
                c.alignment = _align(h='left', v='center')
            elif isinstance(val, (int, float)) and val is not None:
                c.number_format = '#,##0.00'
                c.font          = _font(bold=True, size=10, color=COLOR_TOTAL_FG)
                c.alignment     = _align(h='right', v='center')
            else:
                c.font      = _font(bold=True, size=10, color=COLOR_TOTAL_FG)
                c.alignment = _align(h='center', v='center')

        ws.row_dimensions[row].height = 17

    def escribir_subencabezado(self, ws, row: int, ncols: int, texto: str):
        """Fila de sub-encabezado (ej: separador de secciones)."""
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=ncols)
        c = ws.cell(row=row, column=1, value=texto)
        c.font      = _font(bold=True, size=10, color=COLOR_HEADER_FG)
        c.fill      = _fill(COLOR_SUBHEADER)
        c.alignment = _align(h='left', v='center')
        c.border    = _border(COLOR_SUBHEADER)
        ws.row_dimensions[row].height = 16

    def guardar_en_response(self, response: HttpResponse):
        """Serializa el workbook y lo escribe en el HttpResponse."""
        buf = io.BytesIO()
        self.wb.save(buf)
        buf.seek(0)
        response.write(buf.read())

    def guardar_en_bytes(self) -> bytes:
        """Retorna el workbook serializado como bytes (útil para tests)."""
        buf = io.BytesIO()
        self.wb.save(buf)
        buf.seek(0)
        return buf.read()
