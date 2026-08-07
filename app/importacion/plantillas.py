"""Generación de la planilla Excel modelo para la carga inicial de datos (FA5)."""
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.worksheet.worksheet import Worksheet

from app.importacion.definiciones import COLUMNAS_PLANTILLA

TITULO_FILL = PatternFill(start_color="2E86AB", end_color="2E86AB", fill_type="solid")
TITULO_FONT = Font(color="FFFFFF", bold=True)


def _armar_hoja(ws: Worksheet, columnas: list[str]) -> None:
    ws.append(columnas)
    for celda in ws[1]:
        celda.fill = TITULO_FILL
        celda.font = TITULO_FONT
    for i, nombre in enumerate(columnas, start=1):
        ancho = max(14, len(nombre) + 2)
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = ancho


def _armar_hoja_instrucciones(ws: Worksheet) -> None:
    ws.append(["Instrucciones para completar la planilla"])
    ws["A1"].font = Font(bold=True, size=13)
    ws.append([])
    ws.append(["- Completar los datos a partir de la fila 2 de cada hoja (no dejar filas vacías en el medio)."])
    ws.append(["- Columnas de SI / NO: escribir SI o NO."])
    ws.append(["- Columnas que nombran otra entidad (por ejemplo \"Edificio\" en la hoja Unidad,"])
    ws.append(["  o \"Profesional\" en la hoja ReservaRegular) se completan con el nombre o código"])
    ws.append(["  ya cargado en la hoja correspondiente, no con un número interno."])
    ws.append(["- En la hoja ReservaRegular y Placa, la columna \"Profesional\" se completa con el"])
    ws.append(["  Código del profesional (columna IdCodigo de la hoja Profesional)."])
    ws.append(["- Columnas de fecha (FechaNacimiento, VigenciaInicio, VigenciaFin, Fecha, etc.):"])
    ws.append(["  formato DD/MM/AAAA."])
    ws.append(["- ProfesionalCabezaEquipo (solo para categoría E) se completa con el Código del R,"])
    ws.append(["  y ese R tiene que estar cargado ANTES en la misma hoja."])
    ws.append([])
    ws.append(["Orden recomendado de carga: Edificio, Unidad, Consultorio, Profesion, Profesional,"])
    ws.append(["ReservaRegular, Llave, Placa, FechasEspeciales, Responsable."])
    ws.column_dimensions["A"].width = 100


def generar_plantillas(destino: Path | str) -> Path:
    """Genera un único libro Excel con una hoja de instrucciones y una hoja
    por entidad importable (ver app.importacion.definiciones.COLUMNAS_PLANTILLA)."""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook()
    wb.remove(wb.active)

    ws_instrucciones = wb.create_sheet(title="Instrucciones")
    _armar_hoja_instrucciones(ws_instrucciones)

    for entidad, columnas in COLUMNAS_PLANTILLA.items():
        ws = wb.create_sheet(title=entidad[:31])
        _armar_hoja(ws, columnas)
    wb.save(destino)
    return destino
