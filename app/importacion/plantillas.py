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
    ws.append(["- En la hoja ReservaRegular, Placa y PlanPago, la columna \"Profesional\" se completa"])
    ws.append(["  con el Código del profesional (columna IdCodigo de la hoja Profesional)."])
    ws.append(["- Columnas de fecha (FechaNacimiento, VigenciaInicio, VigenciaFin, Fecha, etc.):"])
    ws.append(["  formato DD/MM/AAAA."])
    ws.append(["- ProfesionalCabezaEquipo (solo para categoría E) se completa con el Código del R,"])
    ws.append(["  y ese R tiene que estar cargado ANTES en la misma hoja."])
    ws.append([])
    ws.append(["Hoja PlanPago (opcional): para dar de alta planes de pago ya acordados y en curso"])
    ws.append(["antes de empezar a usar el sistema (no hace falta para planes nuevos, esos se cargan"])
    ws.append(["desde la pantalla de Planes de pago)."])
    ws.append(["- MesAnoInicio: formato MM/AAAA (mes de la primera cuota, no el de hoy)."])
    ws.append(["- MontoRefinanciado: el monto original acordado, sin el interés."])
    ws.append(["- PorcentajeInteresMensual: dejar vacío o en 0 si no hay interés."])
    ws.append(["- CantidadCuotas: la cantidad total de cuotas del plan (no las que faltan)."])
    ws.append(["- El importe de cada cuota lo calcula el sistema solo (MontoRefinanciado más el interés,"])
    ws.append(["  dividido CantidadCuotas, todas las cuotas iguales)."])
    ws.append(["- Las cuotas de meses anteriores al de hoy se marcan solas como ya pagadas; no hace"])
    ws.append(["  falta indicar en qué cuota está el profesional actualmente."])
    ws.append([])
    ws.append([])
    ws.append(["Hojas Llave / LlaveAcceso / LlaveMovimiento: tres hojas para cargar las llaves del"])
    ws.append(["espacio, cada una sobre una tabla real distinta — en ese orden, no se puede cargar"])
    ws.append(["LlaveAcceso o LlaveMovimiento sin haber cargado antes el Tipo de llave en la hoja Llave."])
    ws.append(["- Hoja Llave: un Tipo de llave por fila (ej. \"la llave del portón de Ramos 1\"). El"])
    ws.append(["  Nombre lo arma el sistema solo (\"Tipo llave E1\"...) — no hace falta indicarlo."])
    ws.append(["- Columna \"Codigo\" (hoja Llave): inventá un texto corto y único por fila (ej. \"LL-01\","])
    ws.append(["  \"LL-02\"...) — sirve SOLO para que las hojas LlaveAcceso/LlaveMovimiento, más abajo,"])
    ws.append(["  puedan decir a qué Tipo de llave se refiere cada una de sus filas (columna"])
    ws.append(["  \"CodigoLlave\", con el mismo texto). No se guarda en el sistema, es solo de la planilla."])
    ws.append(["- La hoja Llave ingresa sola 1000 copias de stock a cada Tipo que crea, para que la"])
    ws.append(["  hoja LlaveMovimiento nunca falle por falta de stock al asignar — después de importar,"])
    ws.append(["  ajustá el stock real de cada una a mano (Ingresar copia al stock / Registrar pérdida,"])
    ws.append(["  desde la pantalla de Llaves) para que vuelva a reflejar la cantidad real que tenés."])
    ws.append(["- Hoja LlaveAcceso: a qué Edificio (y, si corresponde, qué Unidad puntual) abre cada"])
    ws.append(["  Tipo de llave."])
    ws.append(["- Hoja LlaveMovimiento: quién tiene en su poder cada copia (columna \"Profesional\","])
    ws.append(["  por Código), y si ya abonó el depósito o fue bonificado (columna \"DepositoAbonado\")"])
    ws.append(["  — una fila por cada copia ya repartida. No genera ningún cargo nuevo: es la tenencia"])
    ws.append(["  tal cual ya estaba, de antes de empezar a usar el sistema."])
    ws.append([])
    ws.append(["Orden recomendado de carga: Localidad, Edificio, Unidad, Consultorio, Profesion,"])
    ws.append(["Profesional, ReservaRegular, Llave, LlaveAcceso, LlaveMovimiento, Placa,"])
    ws.append(["FechasEspeciales, Responsable, PlanPago."])
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
