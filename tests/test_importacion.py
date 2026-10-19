import pytest
from openpyxl import load_workbook

from app.db.init_db import init_database
from app.db.seed import sembrar_configuracion
from app.importacion.importar_excel import importar_planilla
from app.importacion.plantillas import generar_plantillas
from app.negocio.llaves import resumen_stock
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    yield connection
    connection.close()


def test_generar_plantilla_crea_una_hoja_por_entidad(tmp_path):
    ruta = generar_plantillas(tmp_path / "plantilla.xlsx")
    assert ruta.exists()

    wb = load_workbook(ruta)
    assert "Localidad" in wb.sheetnames
    assert "Edificio" in wb.sheetnames
    assert "Unidad" in wb.sheetnames
    assert "Consultorio" in wb.sheetnames
    assert wb["Localidad"][1][0].value == "Localidad"
    assert wb["Edificio"][1][0].value == "Nombre"


def test_importar_edificio_unidad_consultorio(conn, tmp_path):
    ruta = generar_plantillas(tmp_path / "plantilla.xlsx")
    wb = load_workbook(ruta)

    wb["Localidad"].append(["Ramos Mejía", "La Matanza", "Buenos Aires", "Argentina"])
    wb["Edificio"].append(["Ramos 1", "Av. Rivadavia 13876", "Ramos Mejía"])

    wb["Unidad"].append(
        ["Ramos 1", '7mo "L"', "SI", "SI", 2, "NO", "NO", "NO", "NO", "NO", "NO", "SI", 60]
    )

    wb["Consultorio"].append(
        ["Ramos 1", '7mo "L"', 3, 4.2, 3.5, 1.2, 0.6, "intermedio", "SI", "NO", "SI", "NO", "SI", "SI", "NO", 4646, 4646]
    )

    wb.save(ruta)

    resultados = {r.entidad: r for r in importar_planilla(conn, ruta)}

    assert resultados["Edificio"].filas_importadas == 1
    assert resultados["Unidad"].filas_importadas == 1
    assert resultados["Consultorio"].filas_importadas == 1
    assert not resultados["Unidad"].errores
    assert not resultados["Consultorio"].errores

    edificio = obtener_repositorio(conn, "Edificio").listar()[0]
    unidad = obtener_repositorio(conn, "Unidad").listar()[0]
    consultorio = obtener_repositorio(conn, "Consultorio").listar()[0]

    assert unidad["IdEdificio"] == edificio["IdEdificio"]
    assert unidad["WiFi"] == 1
    assert consultorio["IdUnidad"] == unidad["IdUnidad"]
    assert consultorio["NumeroConsultorio"] == 3
    assert consultorio["LargoEscritorio"] == 1.2
    assert consultorio["AnchoEscritorio"] == 0.6

    localidad = obtener_repositorio(conn, "Localidad").listar()[0]
    assert localidad["Localidad"] == "Ramos Mejía"
    assert localidad["Partido"] == "La Matanza"
    assert edificio["IdLocalidad"] == localidad["IdLocalidad"]


def test_importar_edificio_con_localidad_inexistente_reporta_error(conn, tmp_path):
    ruta = generar_plantillas(tmp_path / "plantilla.xlsx")
    wb = load_workbook(ruta)
    wb["Edificio"].append(["Ramos 1", "Av. Rivadavia 13876", "Localidad Que No Existe"])
    wb.save(ruta)

    resultados = {r.entidad: r for r in importar_planilla(conn, ruta)}

    assert resultados["Edificio"].filas_importadas == 0
    assert len(resultados["Edificio"].errores) == 1
    assert "Localidad Que No Existe" in resultados["Edificio"].errores[0]


def test_importar_referencia_inexistente_reporta_error(conn, tmp_path):
    ruta = generar_plantillas(tmp_path / "plantilla.xlsx")
    wb = load_workbook(ruta)

    wb["Unidad"].append(
        ["Edificio Que No Existe", "PB", "NO", "NO", 1, "NO", "NO", "NO", "NO", "NO", "NO", "NO", 10]
    )
    wb.save(ruta)

    resultados = {r.entidad: r for r in importar_planilla(conn, ruta)}

    assert resultados["Unidad"].filas_importadas == 0
    assert len(resultados["Unidad"].errores) == 1
    assert "Edificio Que No Existe" in resultados["Unidad"].errores[0]


def test_importar_convierte_fecha_dd_mm_aaaa_a_iso(conn, tmp_path):
    ruta = generar_plantillas(tmp_path / "plantilla.xlsx")
    wb = load_workbook(ruta)
    wb["Localidad"].append(["Ramos Mejía", "La Matanza", "Buenos Aires", "Argentina"])
    wb["Edificio"].append(["Ramos 1", "Av. Rivadavia 13876", "Ramos Mejía"])
    wb["Unidad"].append(
        ["Ramos 1", '7mo "L"', "SI", "SI", 2, "NO", "NO", "NO", "NO", "NO", "NO", "SI", 60]
    )
    wb["Consultorio"].append(
        ["Ramos 1", '7mo "L"', 3, 4.2, 3.5, 1.2, 0.6, "intermedio", "SI", "NO", "SI", "NO", "SI", "SI", "NO", 4646, 4646]
    )
    wb["Profesional"].append(
        ["R", "R1", "Lo Veci", "María Virginia Lo Veci", "Virginia", "Virgi", "Femenino",
         "28456789", "27-28456789-3", "Monotributo", "15/03/1985", "Av. San Martín 1234", "Ramos Mejía",
         None, "1145678901", None, None, "Lic.", None, None, None, None, None, None, None]
    )
    wb["ReservaRegular"].append(
        ["R1", "Ramos 1", '7mo "L"', "3", "Lunes", "14", "18", "01/08/2026", None, "NO", None]
    )
    wb.save(ruta)

    resultados = {r.entidad: r for r in importar_planilla(conn, ruta)}
    assert not resultados["Profesional"].errores
    assert not resultados["ReservaRegular"].errores

    profesional = obtener_repositorio(conn, "Profesional").listar()[0]
    assert profesional["FechaNacimiento"] == "1985-03-15"
    reserva = obtener_repositorio(conn, "ReservaRegular").listar()[0]
    assert reserva["VigenciaInicio"] == "2026-08-01"


def test_importar_fecha_invalida_reporta_error_de_fila(conn, tmp_path):
    ruta = generar_plantillas(tmp_path / "plantilla.xlsx")
    wb = load_workbook(ruta)
    wb["Localidad"].append(["Ramos Mejía", "La Matanza", "Buenos Aires", "Argentina"])
    wb["Edificio"].append(["Ramos 1", "Av. Rivadavia 13876", "Ramos Mejía"])
    wb["Unidad"].append(
        ["Ramos 1", '7mo "L"', "SI", "SI", 2, "NO", "NO", "NO", "NO", "NO", "NO", "SI", 60]
    )
    wb["Consultorio"].append(
        ["Ramos 1", '7mo "L"', 3, 4.2, 3.5, 1.2, 0.6, "intermedio", "SI", "NO", "SI", "NO", "SI", "SI", "NO", 4646, 4646]
    )
    wb["Profesional"].append(
        ["R", "R1", "Lo Veci", "María Virginia Lo Veci", "Virginia", "Virgi", "Femenino",
         "28456789", "27-28456789-3", "Monotributo", "1985-03-15", "Av. San Martín 1234", "Ramos Mejía",
         None, "1145678901", None, None, "Lic.", None, None, None, None, None, None, None]
    )
    wb.save(ruta)

    resultados = {r.entidad: r for r in importar_planilla(conn, ruta)}
    assert resultados["Profesional"].filas_importadas == 0
    assert len(resultados["Profesional"].errores) == 1
    assert "FechaNacimiento" in resultados["Profesional"].errores[0]


def test_importar_profesional_cabeza_de_equipo(conn, tmp_path):
    ruta = generar_plantillas(tmp_path / "plantilla.xlsx")
    wb = load_workbook(ruta)
    fila_r = ["R", "R1", "Lo Veci", "María Virginia Lo Veci", "Virginia", "Virgi", "Femenino",
              "28456789", "27-28456789-3", "Monotributo", None, None, None, None, "1145678901",
              None, None, "Lic.", None, None, None, None, None, None, None, None]
    fila_e = ["E", "E1", "Gomez", "Ana Gomez", "Ana", None, "Femenino",
              "30111222", "27-30111222-3", "Monotributo", None, None, None, None, "1145678902",
              None, None, "Lic.", None, None, None, None, "R1", None, None, None]
    wb["Profesional"].append(fila_r)
    wb["Profesional"].append(fila_e)
    wb.save(ruta)

    resultados = {r.entidad: r for r in importar_planilla(conn, ruta)}
    assert not resultados["Profesional"].errores
    assert resultados["Profesional"].filas_importadas == 2

    r1 = obtener_repositorio(conn, "Profesional").listar(IdCodigo="R1")[0]
    e1 = obtener_repositorio(conn, "Profesional").listar(IdCodigo="E1")[0]
    assert e1["ProfesionalCabezaEquipo"] == r1["IdProfesional"]


def test_importar_saldo_cuenta_anterior(conn, tmp_path):
    ruta = generar_plantillas(tmp_path / "plantilla.xlsx")
    wb = load_workbook(ruta)
    encabezados = [c.value for c in wb["Profesional"][1]]
    assert "SaldoCuentaAnterior" in encabezados
    columna_saldo = encabezados.index("SaldoCuentaAnterior")

    fila = [None] * len(encabezados)
    fila[encabezados.index("CategoriaProfesional")] = "R"
    fila[encabezados.index("IdCodigo")] = "R1"
    fila[encabezados.index("Apellido")] = "Lo Veci"
    fila[columna_saldo] = 15000.50
    wb["Profesional"].append(fila)
    wb.save(ruta)

    resultados = {r.entidad: r for r in importar_planilla(conn, ruta)}
    assert not resultados["Profesional"].errores

    r1 = obtener_repositorio(conn, "Profesional").listar(IdCodigo="R1")[0]
    assert r1["SaldoCuentaAnterior"] == 15000.50


def test_importar_fechas_especiales(conn, tmp_path):
    ruta = generar_plantillas(tmp_path / "plantilla.xlsx")
    wb = load_workbook(ruta)
    wb["FechasEspeciales"].append(["25/05/2026", "Día de la Patria", "Feriado nacional"])
    wb.save(ruta)

    resultados = {r.entidad: r for r in importar_planilla(conn, ruta)}
    assert resultados["FechasEspeciales"].filas_importadas == 1
    fecha = obtener_repositorio(conn, "FechasEspeciales").listar()[0]
    assert fecha["Fecha"] == "2026-05-25"
    assert fecha["Tipo"] == "Feriado nacional"


# --------------------------------------------------------------- PlanPago

def _fijar_fecha(conn, fecha_iso: str) -> None:
    sembrar_configuracion(conn)
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = ? WHERE IdConfiguracion = 1",
        (fecha_iso,),
    )
    conn.commit()


def _agregar_profesional_r1(wb) -> None:
    encabezados = [c.value for c in wb["Profesional"][1]]
    fila = [None] * len(encabezados)
    fila[encabezados.index("CategoriaProfesional")] = "R"
    fila[encabezados.index("IdCodigo")] = "R1"
    fila[encabezados.index("Apellido")] = "Lo Veci"
    wb["Profesional"].append(fila)


def test_importar_plan_pago_calcula_cuota_y_marca_pasadas_pagadas(conn, tmp_path):
    """Plan acordado en mayo por 12 cuotas de $1000, importado el 15/8: las
    cuotas de mayo/junio/julio (ya transcurridas) quedan solas como
    pagadas, la de agosto (período actual) y las siguientes, pendientes."""
    _fijar_fecha(conn, "2026-08-15")
    ruta = generar_plantillas(tmp_path / "plantilla.xlsx")
    wb = load_workbook(ruta)
    _agregar_profesional_r1(wb)
    wb["PlanPago"].append(["R1", "05/2026", 12000, 0, 12, "Plan acordado antes del sistema"])
    wb.save(ruta)

    resultados = {r.entidad: r for r in importar_planilla(conn, ruta)}
    assert not resultados["PlanPago"].errores
    assert resultados["PlanPago"].filas_importadas == 1

    plan = obtener_repositorio(conn, "PlanPago").listar()[0]
    assert plan["MesAnoInicio"] == "2026-05"
    assert plan["CantidadCuotas"] == 12
    assert plan["ImportePorCuota"] == 1000.0
    assert plan["Estado"] == "Activo"

    cuotas = {c["PeriodoImputado"]: c for c in obtener_repositorio(conn, "CuotaPlan").listar(IdPlan=plan["IdPlan"])}
    assert cuotas["2026-05"]["Estado"] == "Pagada"
    assert cuotas["2026-06"]["Estado"] == "Pagada"
    assert cuotas["2026-07"]["Estado"] == "Pagada"
    assert cuotas["2026-08"]["Estado"] == "Pendiente"
    assert cuotas["2026-09"]["Estado"] == "Pendiente"


def test_importar_plan_pago_calcula_interes(conn, tmp_path):
    _fijar_fecha(conn, "2026-08-15")
    ruta = generar_plantillas(tmp_path / "plantilla.xlsx")
    wb = load_workbook(ruta)
    _agregar_profesional_r1(wb)
    wb["PlanPago"].append(["R1", "08/2026", 10000, 5, 4, None])
    wb.save(ruta)

    resultados = {r.entidad: r for r in importar_planilla(conn, ruta)}
    assert not resultados["PlanPago"].errores
    plan = obtener_repositorio(conn, "PlanPago").listar()[0]
    # 10000 * (1 + 0.05 * 4) = 12000 total / 4 cuotas = 3000 cada una.
    assert plan["MontoTotalAPagar"] == 12000.0
    assert plan["ImportePorCuota"] == 3000.0


def test_importar_plan_pago_referencia_profesional_inexistente(conn, tmp_path):
    ruta = generar_plantillas(tmp_path / "plantilla.xlsx")
    wb = load_workbook(ruta)
    wb["PlanPago"].append(["R99", "05/2026", 12000, 0, 12, None])
    wb.save(ruta)

    resultados = {r.entidad: r for r in importar_planilla(conn, ruta)}
    assert resultados["PlanPago"].filas_importadas == 0
    assert "R99" in resultados["PlanPago"].errores[0]


def test_importar_plan_pago_periodo_invalido_reporta_error(conn, tmp_path):
    ruta = generar_plantillas(tmp_path / "plantilla.xlsx")
    wb = load_workbook(ruta)
    _agregar_profesional_r1(wb)
    wb["PlanPago"].append(["R1", "2026-05", 12000, 0, 12, None])  # formato incorrecto
    wb.save(ruta)

    resultados = {r.entidad: r for r in importar_planilla(conn, ruta)}
    assert resultados["PlanPago"].filas_importadas == 0
    assert "MesAnoInicio" in resultados["PlanPago"].errores[0]


def test_importar_plan_pago_falta_columna_obligatoria(conn, tmp_path):
    ruta = generar_plantillas(tmp_path / "plantilla.xlsx")
    wb = load_workbook(ruta)
    _agregar_profesional_r1(wb)
    wb["PlanPago"].append(["R1", "05/2026", None, 0, 12, None])  # sin MontoRefinanciado
    wb.save(ruta)

    resultados = {r.entidad: r for r in importar_planilla(conn, ruta)}
    assert resultados["PlanPago"].filas_importadas == 0
    assert "MontoRefinanciado" in resultados["PlanPago"].errores[0]


def test_importar_plan_pago_ya_existe_en_plantilla(tmp_path):
    ruta = generar_plantillas(tmp_path / "plantilla.xlsx")
    wb = load_workbook(ruta)
    assert "PlanPago" in wb.sheetnames
    assert [c.value for c in wb["PlanPago"][1]] == [
        "Profesional", "MesAnoInicio", "MontoRefinanciado",
        "PorcentajeInteresMensual", "CantidadCuotas", "Observacion",
    ]


def test_importar_alias_banos_con_tilde(conn, tmp_path):
    ruta = generar_plantillas(tmp_path / "plantilla.xlsx")
    wb = load_workbook(ruta)
    wb["Localidad"].append(["Ramos Mejía", "La Matanza", "Buenos Aires", "Argentina"])
    wb["Edificio"].append(["Ramos 1", "Av. Rivadavia 13876", "Ramos Mejía"])
    ws_unidad = wb["Unidad"]
    ws_unidad.cell(row=1, column=5, value="Baños")  # encabezado con tilde, en vez de "Banos"
    ws_unidad.append(["Ramos 1", '7mo "L"', "SI", "SI", 2, "NO", "NO", "NO", "NO", "NO", "NO", "SI", 60])
    wb.save(ruta)

    resultados = {r.entidad: r for r in importar_planilla(conn, ruta)}
    assert not resultados["Unidad"].errores
    unidad = obtener_repositorio(conn, "Unidad").listar()[0]
    assert unidad["Banos"] == 2


# --------------------------------------------------------------- Llaves
# (tres hojas: Llave -> LlaveAcceso -> LlaveMovimiento, ver el docstring
# nuevo de COLUMNAS_PLANTILLA en definiciones.py para el porqué)

def test_importar_llave_guarda_observacion_y_codigo(conn, tmp_path):
    ruta = generar_plantillas(tmp_path / "plantilla.xlsx")
    wb = load_workbook(ruta)
    wb["Llave"].append(["LL-01", "Edificio", 500, "Llave del portón"])
    wb.save(ruta)

    resultados = {r.entidad: r for r in importar_planilla(conn, ruta)}
    assert resultados["Llave"].filas_importadas == 1
    assert not resultados["Llave"].errores

    llave = obtener_repositorio(conn, "Llave").listar()[0]
    assert llave["Tipo"] == "Edificio"
    assert llave["ValorDepositoActual"] == 500
    assert llave["Observacion"] == "Llave del portón"
    # Sin ninguna columna "Nombre" en la planilla -- lo arma el sistema
    # solo, SIN sufijo de edificio (el Edificio recién se sabe en la hoja
    # "LlaveAcceso", que todavía no corrió acá).
    assert llave["Nombre"] == "Tipo llave E1"


def test_importar_llave_ingresa_stock_inicial(conn, tmp_path):
    ruta = generar_plantillas(tmp_path / "plantilla.xlsx")
    wb = load_workbook(ruta)
    wb["Llave"].append(["LL-01", "No especificada", 0, None])
    wb.save(ruta)

    importar_planilla(conn, ruta)
    llave = obtener_repositorio(conn, "Llave").listar()[0]
    assert resumen_stock(conn, llave["IdLlave"]) == {
        "ingresadas": 1000, "perdidas": 0, "existentes": 1000, "asignadas": 0, "disponibles": 1000,
    }


def test_importar_llave_sin_codigo_reporta_error_y_no_rompe_las_demas_filas(conn, tmp_path):
    ruta = generar_plantillas(tmp_path / "plantilla.xlsx")
    wb = load_workbook(ruta)
    wb["Llave"].append([None, "Edificio", 500, None])  # Código vacío
    wb["Llave"].append(["LL-01", "Unidad", 300, None])
    wb.save(ruta)

    resultados = {r.entidad: r for r in importar_planilla(conn, ruta)}
    assert resultados["Llave"].filas_importadas == 1
    assert len(resultados["Llave"].errores) == 1
    assert "Codigo" in resultados["Llave"].errores[0]

    llave = obtener_repositorio(conn, "Llave").listar()[0]
    assert llave["Tipo"] == "Unidad"


def test_importar_llave_sin_tipo_reporta_error_y_no_rompe_las_demas_filas(conn, tmp_path):
    ruta = generar_plantillas(tmp_path / "plantilla.xlsx")
    wb = load_workbook(ruta)
    wb["Llave"].append(["LL-01", None, 500, None])  # Tipo vacío -- antes rompía con KeyError
    wb["Llave"].append(["LL-02", "Unidad", 300, None])
    wb.save(ruta)

    resultados = {r.entidad: r for r in importar_planilla(conn, ruta)}
    assert resultados["Llave"].filas_importadas == 1
    assert len(resultados["Llave"].errores) == 1
    assert "Tipo de llave inválido" in resultados["Llave"].errores[0]

    llave = obtener_repositorio(conn, "Llave").listar()[0]
    assert llave["Tipo"] == "Unidad"


def test_importar_llave_codigo_duplicado_en_la_misma_hoja_reporta_error(conn, tmp_path):
    ruta = generar_plantillas(tmp_path / "plantilla.xlsx")
    wb = load_workbook(ruta)
    wb["Llave"].append(["LL-01", "Edificio", 500, "La primera"])
    wb["Llave"].append(["LL-01", "Unidad", 300, "La segunda, mismo código"])
    wb.save(ruta)

    resultados = {r.entidad: r for r in importar_planilla(conn, ruta)}
    assert resultados["Llave"].filas_importadas == 1
    assert len(resultados["Llave"].errores) == 1
    assert "LL-01" in resultados["Llave"].errores[0]
    assert len(obtener_repositorio(conn, "Llave").listar()) == 1


def test_importar_llave_duplicada_no_se_vuelve_a_crear(conn, tmp_path):
    """Mismo criterio que el resto de las entidades: mismo Tipo/
    ValorDepositoActual/Observacion ya cargado = duplicado, no se crea de
    nuevo -- comparado sin "Codigo" (planilla-only, nunca llega a ser
    columna de la tabla) ni "Nombre" (autogenerado, siempre distinto)."""
    ruta = generar_plantillas(tmp_path / "plantilla.xlsx")
    wb = load_workbook(ruta)
    wb["Llave"].append(["LL-01", "Edificio", 500, "Llave del portón"])
    wb.save(ruta)
    importar_planilla(conn, ruta)

    resultado = {r.entidad: r for r in importar_planilla(conn, ruta)}
    assert resultado["Llave"].filas_importadas == 0
    assert resultado["Llave"].filas_duplicadas == 1
    assert len(obtener_repositorio(conn, "Llave").listar()) == 1


def test_importar_llaveacceso_crea_el_acceso(conn, tmp_path):
    ruta = generar_plantillas(tmp_path / "plantilla.xlsx")
    wb = load_workbook(ruta)
    wb["Edificio"].append(["Ramos 1"])
    wb["Llave"].append(["LL-01", "Edificio", 500, "Llave del portón"])
    wb["LlaveAcceso"].append(["LL-01", "Ramos 1", None, "Portón principal", None])
    wb.save(ruta)

    resultados = {r.entidad: r for r in importar_planilla(conn, ruta)}
    assert resultados["LlaveAcceso"].filas_importadas == 1
    assert not resultados["LlaveAcceso"].errores

    llave = obtener_repositorio(conn, "Llave").listar()[0]
    id_edificio = obtener_repositorio(conn, "Edificio").listar()[0]["IdEdificio"]
    accesos = obtener_repositorio(conn, "LlaveAcceso").listar(IdLlave=llave["IdLlave"])
    assert len(accesos) == 1
    assert accesos[0]["IdEdificio"] == id_edificio
    assert accesos[0]["IdUnidad"] is None
    assert accesos[0]["Nombre"] == "Portón principal"


def test_importar_llaveacceso_con_codigo_inexistente_reporta_error(conn, tmp_path):
    ruta = generar_plantillas(tmp_path / "plantilla.xlsx")
    wb = load_workbook(ruta)
    wb["Edificio"].append(["Ramos 1"])
    wb["LlaveAcceso"].append(["LL-NO-EXISTE", "Ramos 1", None, None, None])
    wb.save(ruta)

    resultados = {r.entidad: r for r in importar_planilla(conn, ruta)}
    assert resultados["LlaveAcceso"].filas_importadas == 0
    assert "LL-NO-EXISTE" in resultados["LlaveAcceso"].errores[0]
    assert obtener_repositorio(conn, "LlaveAcceso").listar() == []


def test_importar_llaveacceso_con_edificio_inexistente_reporta_error(conn, tmp_path):
    ruta = generar_plantillas(tmp_path / "plantilla.xlsx")
    wb = load_workbook(ruta)
    wb["Llave"].append(["LL-01", "Edificio", 500, None])
    wb["LlaveAcceso"].append(["LL-01", "No existe este edificio", None, None, None])
    wb.save(ruta)

    resultados = {r.entidad: r for r in importar_planilla(conn, ruta)}
    assert resultados["LlaveAcceso"].filas_importadas == 0
    assert "No se encontró el edificio" in resultados["LlaveAcceso"].errores[0]


def test_importar_llavemovimiento_con_deposito_abonado_no_genera_cargo(conn, tmp_path):
    """Tenencia histórica: si ya pagó el depósito, fue por fuera del
    sistema -- la importación lo deja registrado en el movimiento, pero
    nunca genera un CargoEspecial nuevo (no hay nada pendiente de cobrar)."""
    ruta = generar_plantillas(tmp_path / "plantilla.xlsx")
    wb = load_workbook(ruta)
    _agregar_profesional_r1(wb)
    wb["Llave"].append(["LL-01", "No especificada", 500, None])
    wb["LlaveMovimiento"].append(["LL-01", "R1", "SI"])
    wb.save(ruta)

    resultados = {r.entidad: r for r in importar_planilla(conn, ruta)}
    assert resultados["LlaveMovimiento"].filas_importadas == 1
    assert not resultados["LlaveMovimiento"].errores

    llave = obtener_repositorio(conn, "Llave").listar()[0]
    movimientos = obtener_repositorio(conn, "LlaveMovimiento").listar(IdLlave=llave["IdLlave"])
    asignacion = next(m for m in movimientos if m["Tipo"] == "Asignación")
    assert asignacion["DepositoCobrado"] == 1
    assert asignacion["MontoCobrado"] == 500
    assert obtener_repositorio(conn, "CargoEspecial").listar() == []
    # Consume del stock inicial precargado por la hoja "Llave", no de uno
    # ingresado aparte por esta hoja.
    assert resumen_stock(conn, llave["IdLlave"])["disponibles"] == 999


def test_importar_llavemovimiento_sin_deposito_abonado(conn, tmp_path):
    ruta = generar_plantillas(tmp_path / "plantilla.xlsx")
    wb = load_workbook(ruta)
    _agregar_profesional_r1(wb)
    wb["Llave"].append(["LL-01", "No especificada", 500, None])
    wb["LlaveMovimiento"].append(["LL-01", "R1", "NO"])
    wb.save(ruta)

    resultados = {r.entidad: r for r in importar_planilla(conn, ruta)}
    assert resultados["LlaveMovimiento"].filas_importadas == 1

    llave = obtener_repositorio(conn, "Llave").listar()[0]
    asignacion = next(
        m for m in obtener_repositorio(conn, "LlaveMovimiento").listar(IdLlave=llave["IdLlave"])
        if m["Tipo"] == "Asignación"
    )
    assert asignacion["DepositoCobrado"] == 0
    assert asignacion["MontoCobrado"] is None


def test_importar_llavemovimiento_con_profesional_inexistente_reporta_error(conn, tmp_path):
    ruta = generar_plantillas(tmp_path / "plantilla.xlsx")
    wb = load_workbook(ruta)
    wb["Llave"].append(["LL-01", "No especificada", 500, None])
    wb["LlaveMovimiento"].append(["LL-01", "R99", "NO"])
    wb.save(ruta)

    resultados = {r.entidad: r for r in importar_planilla(conn, ruta)}
    assert resultados["LlaveMovimiento"].filas_importadas == 0
    assert "No se encontró el profesional con código" in resultados["LlaveMovimiento"].errores[0]


def test_importar_llavemovimiento_con_codigo_inexistente_reporta_error(conn, tmp_path):
    ruta = generar_plantillas(tmp_path / "plantilla.xlsx")
    wb = load_workbook(ruta)
    _agregar_profesional_r1(wb)
    wb["LlaveMovimiento"].append(["LL-NO-EXISTE", "R1", "NO"])
    wb.save(ruta)

    resultados = {r.entidad: r for r in importar_planilla(conn, ruta)}
    assert resultados["LlaveMovimiento"].filas_importadas == 0
    assert "LL-NO-EXISTE" in resultados["LlaveMovimiento"].errores[0]


def test_importar_llave_acceso_y_movimiento_enlazan_por_codigo(conn, tmp_path):
    """De punta a punta, las tres hojas juntas: el mismo "Codigo" de la
    hoja Llave resuelve tanto el acceso como la tenencia al MISMO
    IdLlave."""
    ruta = generar_plantillas(tmp_path / "plantilla.xlsx")
    wb = load_workbook(ruta)
    wb["Edificio"].append(["Ramos 1"])
    _agregar_profesional_r1(wb)
    wb["Llave"].append(["LL-01", "Edificio", 500, "Llave del portón"])
    wb["LlaveAcceso"].append(["LL-01", "Ramos 1", None, None, None])
    wb["LlaveMovimiento"].append(["LL-01", "R1", "SI"])
    wb.save(ruta)

    resultados = {r.entidad: r for r in importar_planilla(conn, ruta)}
    assert resultados["Llave"].filas_importadas == 1
    assert resultados["LlaveAcceso"].filas_importadas == 1
    assert resultados["LlaveMovimiento"].filas_importadas == 1

    llave = obtener_repositorio(conn, "Llave").listar()[0]
    id_edificio = obtener_repositorio(conn, "Edificio").listar()[0]["IdEdificio"]
    acceso = obtener_repositorio(conn, "LlaveAcceso").listar(IdLlave=llave["IdLlave"])[0]
    assert acceso["IdEdificio"] == id_edificio
    asignacion = next(
        m for m in obtener_repositorio(conn, "LlaveMovimiento").listar(IdLlave=llave["IdLlave"])
        if m["Tipo"] == "Asignación"
    )
    assert asignacion["IdLlave"] == llave["IdLlave"]


def test_importar_llave_reimportada_sigue_resolviendo_el_codigo_para_las_otras_hojas(conn, tmp_path):
    """Si toda la planilla se reimporta sin querer, la hoja "Llave" marca
    la fila como duplicada (no crea un Tipo nuevo) -- pero el "Codigo" de
    esa fila sigue resolviendo al Tipo YA existente, para que
    "LlaveAcceso"/"LlaveMovimiento" de esa misma corrida no se queden sin
    poder resolver su "CodigoLlave"."""
    ruta = generar_plantillas(tmp_path / "plantilla.xlsx")
    wb = load_workbook(ruta)
    wb["Edificio"].append(["Ramos 1"])
    wb["Llave"].append(["LL-01", "Edificio", 500, "Llave del portón"])
    wb.save(ruta)
    importar_planilla(conn, ruta)  # primera corrida: crea el Tipo de llave

    ruta2 = generar_plantillas(tmp_path / "plantilla2.xlsx")
    wb2 = load_workbook(ruta2)
    wb2["Edificio"].append(["Ramos 1"])
    wb2["Llave"].append(["LL-01", "Edificio", 500, "Llave del portón"])  # mismo Código, misma llave
    wb2["LlaveAcceso"].append(["LL-01", "Ramos 1", None, None, None])
    wb2.save(ruta2)

    resultados = {r.entidad: r for r in importar_planilla(conn, ruta2)}
    assert resultados["Llave"].filas_importadas == 0
    assert resultados["Llave"].filas_duplicadas == 1
    assert resultados["LlaveAcceso"].filas_importadas == 1  # resolvió el código igual
    assert not resultados["LlaveAcceso"].errores
    assert len(obtener_repositorio(conn, "Llave").listar()) == 1  # sigue habiendo un solo Tipo


# --------------------------------------------------------------- Placa

def _preparar_unidad_con_tablero(wb, *, cant_limite_placas: int) -> None:
    wb["Edificio"].append(["Ramos 1", "Av. Rivadavia 13876", None])
    wb["Unidad"].append(
        ["Ramos 1", '7mo "L"', "NO", "NO", 1, "NO", "NO", "NO", "NO", "NO", "NO", "NO", cant_limite_placas]
    )


def test_importar_placa_posicion_fuera_del_tablero_reporta_error(conn, tmp_path):
    ruta = generar_plantillas(tmp_path / "plantilla.xlsx")
    wb = load_workbook(ruta)
    _preparar_unidad_con_tablero(wb, cant_limite_placas=3)
    _agregar_profesional_r1(wb)
    wb["Placa"].append(["Ramos 1", '7mo "L"', 10, "R1", None, "NO"])
    wb.save(ruta)

    resultados = {r.entidad: r for r in importar_planilla(conn, ruta)}
    assert resultados["Placa"].filas_importadas == 0
    assert len(resultados["Placa"].errores) == 1
    assert "fuera del rango 1-3" in resultados["Placa"].errores[0]
    assert not obtener_repositorio(conn, "Placa").listar()


def test_importar_placa_posicion_dentro_del_tablero_se_guarda(conn, tmp_path):
    ruta = generar_plantillas(tmp_path / "plantilla.xlsx")
    wb = load_workbook(ruta)
    _preparar_unidad_con_tablero(wb, cant_limite_placas=3)
    _agregar_profesional_r1(wb)
    wb["Placa"].append(["Ramos 1", '7mo "L"', 2, "R1", None, "NO"])
    wb.save(ruta)

    resultados = {r.entidad: r for r in importar_planilla(conn, ruta)}
    assert resultados["Placa"].filas_importadas == 1
    assert not resultados["Placa"].errores

    placa = obtener_repositorio(conn, "Placa").listar()[0]
    assert placa["PosicionTablero"] == 2
    r1 = obtener_repositorio(conn, "Profesional").listar(IdCodigo="R1")[0]
    assert placa["IdProfesional"] == r1["IdProfesional"]


# ---------------------------------------- no duplicar registros idénticos

def test_importar_la_misma_fila_dos_veces_no_duplica(conn, tmp_path):
    """Pedido explícito de la clienta: volver a correr la misma planilla
    (o una que se solapa) no tiene que crear un segundo registro
    idéntico."""
    ruta = generar_plantillas(tmp_path / "plantilla.xlsx")
    wb = load_workbook(ruta)
    wb["Localidad"].append(["Ramos Mejía", "La Matanza", "Buenos Aires", "Argentina"])
    wb["Edificio"].append(["Ramos 1", "Av. Rivadavia 13876", "Ramos Mejía"])
    wb.save(ruta)

    primera = {r.entidad: r for r in importar_planilla(conn, ruta)}
    assert primera["Edificio"].filas_importadas == 1
    assert primera["Edificio"].filas_duplicadas == 0

    segunda = {r.entidad: r for r in importar_planilla(conn, ruta)}
    assert segunda["Edificio"].filas_importadas == 0
    assert segunda["Edificio"].filas_duplicadas == 1
    assert not segunda["Edificio"].errores  # un duplicado no es un error

    assert len(obtener_repositorio(conn, "Edificio").listar()) == 1


def test_importar_fila_con_un_campo_distinto_no_es_duplicado(conn, tmp_path):
    ruta = generar_plantillas(tmp_path / "plantilla.xlsx")
    wb = load_workbook(ruta)
    wb["Localidad"].append(["Ramos Mejía", "La Matanza", "Buenos Aires", "Argentina"])
    wb["Edificio"].append(["Ramos 1", "Av. Rivadavia 13876", "Ramos Mejía"])
    wb.save(ruta)
    importar_planilla(conn, ruta)

    ruta2 = generar_plantillas(tmp_path / "plantilla2.xlsx")  # planilla nueva, sin la fila ya importada
    wb2 = load_workbook(ruta2)
    wb2["Edificio"].append(["Ramos 1", "Otro domicilio distinto", "Ramos Mejía"])  # mismo nombre, otro domicilio
    wb2.save(ruta2)
    resultado = {r.entidad: r for r in importar_planilla(conn, ruta2)}

    assert resultado["Edificio"].filas_importadas == 1  # se importa igual, no es idéntico al anterior
    assert resultado["Edificio"].filas_duplicadas == 0
    assert len(obtener_repositorio(conn, "Edificio").listar()) == 2


def test_importar_plan_pago_duplicado_no_se_vuelve_a_crear(conn, tmp_path):
    """Un plan duplicado no debe ni recalcularse ni generar un segundo
    juego de cuotas."""
    _fijar_fecha(conn, "2026-08-15")
    ruta = generar_plantillas(tmp_path / "plantilla.xlsx")
    wb = load_workbook(ruta)
    _agregar_profesional_r1(wb)
    wb["PlanPago"].append(["R1", "05/2026", 12000, 0, 12, "Plan acordado antes del sistema"])
    wb.save(ruta)
    importar_planilla(conn, ruta)

    resultado = {r.entidad: r for r in importar_planilla(conn, ruta)}
    assert resultado["PlanPago"].filas_importadas == 0
    assert resultado["PlanPago"].filas_duplicadas == 1
    assert len(obtener_repositorio(conn, "PlanPago").listar()) == 1
    assert len(obtener_repositorio(conn, "CuotaPlan").listar()) == 12
