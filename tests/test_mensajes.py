from datetime import date

import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.liquidaciones import emitir_liquidacion
from app.negocio.mensajes import (
    _lista_con_y,
    determinar_situacion,
    dias_desde_ultimo_pago,
    mensaje_detalle_reserva_aislada,
    mensaje_disponibilidad_horarios,
    mensaje_grupal,
    mensaje_situacion,
    nombre_para_mensaje,
    plan_activo,
    sustituir_variables,
)
from app.negocio.pagos import crear_plan_pago, registrar_pago
from app.repositorio.registro import obtener_repositorio

PERIODO = "2026-08"


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


@pytest.fixture
def consultorio(conn):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='7mo "L"')
    return obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=1, ValorHoraRegularActual=1000,
    )


def _crear_regular(conn, consultorio, **kwargs):
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Test", **kwargs)
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof, IdConsultorio=consultorio, DiaSemana="Lunes",
        HoraInicio=10, HoraFin=12, VigenciaInicio="2026-01-01",
    )
    return id_prof


def test_nombre_para_mensaje_prioriza_apodo(conn, consultorio):
    id_prof = _crear_regular(conn, consultorio, Apodo="Male", NombrePila="Marcela", Tratamiento="Lic.")
    prof = obtener_repositorio(conn, "Profesional").obtener(id_prof)
    assert nombre_para_mensaje(prof) == "Male"


def test_nombre_para_mensaje_usa_nombre_pila_sin_apodo(conn, consultorio):
    id_prof = _crear_regular(conn, consultorio, NombrePila="Marcela", Tratamiento="Lic.")
    prof = obtener_repositorio(conn, "Profesional").obtener(id_prof)
    assert nombre_para_mensaje(prof) == "Marcela"


def test_nombre_para_mensaje_usa_tratamiento_y_apellido_como_ultimo_recurso(conn, consultorio):
    id_prof = _crear_regular(conn, consultorio, Tratamiento="Lic.")
    prof = obtener_repositorio(conn, "Profesional").obtener(id_prof)
    assert nombre_para_mensaje(prof) == "Lic. Test"


def test_situacion_1_deuda_alta_liquidacion_no_enviada(conn, consultorio):
    id_prof = _crear_regular(conn, consultorio, SaldoCuentaAnterior=50000)
    assert determinar_situacion(conn, id_prof, PERIODO) == "1"


def test_situacion_3_deuda_baja_liquidacion_no_enviada(conn, consultorio):
    id_prof = _crear_regular(conn, consultorio)
    assert determinar_situacion(conn, id_prof, PERIODO) == "3"


def test_situacion_2_liquidacion_enviada_sin_plan(conn, consultorio):
    id_prof = _crear_regular(conn, consultorio)
    id_liq, _ = emitir_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO)
    obtener_repositorio(conn, "LiquidacionEmitida").actualizar(id_liq, EstadoEnvio="Enviada")
    assert determinar_situacion(conn, id_prof, PERIODO) == "2"


def test_situacion_5_con_plan_liquidacion_no_enviada(conn, consultorio):
    id_prof = _crear_regular(conn, consultorio)
    crear_plan_pago(conn, id_profesional=id_prof, monto_refinanciado=3000, cantidad_cuotas=3, mes_ano_inicio=PERIODO)
    assert determinar_situacion(conn, id_prof, PERIODO) == "5"


def test_situacion_4_con_plan_liquidacion_enviada(conn, consultorio):
    id_prof = _crear_regular(conn, consultorio)
    crear_plan_pago(conn, id_profesional=id_prof, monto_refinanciado=3000, cantidad_cuotas=3, mes_ano_inicio=PERIODO)
    id_liq, _ = emitir_liquidacion(conn, id_profesional=id_prof, periodo=PERIODO)
    obtener_repositorio(conn, "LiquidacionEmitida").actualizar(id_liq, EstadoEnvio="Enviada")
    assert determinar_situacion(conn, id_prof, PERIODO) == "4"


def test_situacion_none_para_categoria_sin_liquidacion_propia(conn):
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="A", Apellido="Aislada")
    assert determinar_situacion(conn, id_prof, PERIODO) is None


def test_mensaje_situacion_incluye_nombre_y_saldo(conn, consultorio):
    id_prof = _crear_regular(conn, consultorio, Apodo="Male", SaldoCuentaAnterior=50000)
    texto = mensaje_situacion(conn, id_prof, PERIODO)
    assert "Male" in texto
    assert "50.000" in texto


def test_mensaje_situacion_rechaza_categoria_no_r(conn):
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="A", Apellido="Aislada")
    with pytest.raises(ValueError):
        mensaje_situacion(conn, id_prof, PERIODO)


def test_mensaje_situacion_usa_la_plantilla_editada(conn, consultorio):
    """Sección 11: una vez sembrados como predefinidos editables, un
    cambio en la biblioteca tiene que reflejarse en el mensaje real."""
    id_prof = _crear_regular(conn, consultorio, Apodo="Male", SaldoCuentaAnterior=50000)
    mensaje = obtener_repositorio(conn, "MensajePredefinido").listar(
        Descripcion="Situación 1 — Deuda sobre tolerancia",
    )[0]
    obtener_repositorio(conn, "MensajePredefinido").actualizar(
        mensaje["IdMensaje"], Mensaje="Texto editado a mano para {nombre}, debe {saldo}.",
    )
    texto = mensaje_situacion(conn, id_prof, PERIODO)
    assert texto == "Texto editado a mano para Male, debe $ 50.000,00."


def test_mensaje_situacion_usa_fallback_si_la_plantilla_esta_desactivada(conn, consultorio):
    id_prof = _crear_regular(conn, consultorio, Apodo="Male", SaldoCuentaAnterior=50000)
    mensaje = obtener_repositorio(conn, "MensajePredefinido").listar(
        Descripcion="Situación 1 — Deuda sobre tolerancia",
    )[0]
    obtener_repositorio(conn, "MensajePredefinido").actualizar(mensaje["IdMensaje"], Activo=0)
    texto = mensaje_situacion(conn, id_prof, PERIODO)
    assert "Male" in texto
    assert "50.000" in texto


def test_mensaje_situacion_usa_fallback_sin_seed(tmp_path):
    """Sin sembrar_valores_por_defecto (instalación antigua ya
    inicializada antes de este cambio) las situaciones siguen andando
    con el texto fijo — la biblioteca vacía no puede romper el flujo."""
    conn = init_database(tmp_path / "sin_seed.db")
    id_prof = obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="R", Apellido="Test", Apodo="Male", SaldoCuentaAnterior=50000,
    )
    texto = mensaje_situacion(conn, id_prof, PERIODO)
    assert "Male" in texto
    assert "50.000" in texto
    conn.close()


def test_lista_con_y_gramatica():
    assert _lista_con_y([]) == ""
    assert _lista_con_y(["X"]) == "X"
    assert _lista_con_y(["X", "Z"]) == "X y Z"
    assert _lista_con_y(["X", "Z", "W"]) == "X, Z y W"


def test_mensaje_grupal_sin_feriados(conn):
    texto = mensaje_grupal(conn, PERIODO)
    assert "LIQUIDACIONES DE SEPTIEMBRE" in texto
    assert "FERIADOS" not in texto


def test_mensaje_grupal_con_un_feriado_concuerda_en_singular(conn):
    obtener_repositorio(conn, "FechasEspeciales").crear(Fecha="2026-09-07", Tipo="Feriado nacional")
    texto = mensaje_grupal(conn, PERIODO)
    assert "hay un feriado" in texto
    assert "se descuenta al 100%" in texto
    assert "la de octubre" in texto


def test_mensaje_grupal_con_varios_feriados_concuerda_en_plural(conn):
    obtener_repositorio(conn, "FechasEspeciales").crear(Fecha="2026-09-07", Tipo="Feriado nacional")
    obtener_repositorio(conn, "FechasEspeciales").crear(Fecha="2026-09-21", Tipo="Día no laborable")
    texto = mensaje_grupal(conn, PERIODO)
    assert "hay feriados" in texto
    assert "se descuentan al 100%" in texto
    assert " y " in texto


@pytest.fixture
def profesional_aislada_con_edificios(conn):
    id_ed1 = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1", Domicilio="Av. Rivadavia 1234", DomicilioLocalidad="CABA")
    id_ed2 = obtener_repositorio(conn, "Edificio").crear(Nombre="San Justo 1", Domicilio="Belgrano 500", DomicilioLocalidad="San Justo")
    id_un1 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_ed1, Departamento="7mo L")
    id_un2 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_ed2, Departamento="3ro B")
    c1 = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_un1, NumeroConsultorio=1, ValorHoraAisladaActual=500)
    c2 = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_un2, NumeroConsultorio=2, ValorHoraAisladaActual=600)
    id_prof = obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="A", Apellido="Aislada", Apodo="Lu", SaldoCuentaAnterior=1000,
    )
    return id_prof, c1, c2, id_ed1, id_ed2


def test_detalle_aislada_calcula_saldo_a_abonar(conn, profesional_aislada_con_edificios):
    id_prof, c1, c2, _, _ = profesional_aislada_con_edificios
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=c1, Fecha="2026-08-05", HoraInicio=10, HoraFin=12,
        Estado="Confirmada", AplicaRecargo=0,
    )
    registrar_pago(conn, id_profesional=id_prof, monto=500, fecha="2026-08-15", periodo_imputado="2026-08")

    texto = mensaje_detalle_reserva_aislada(conn, id_profesional=id_prof, periodo="2026-08")
    # saldo_anterior 1000 + reserva (2hs x 500) 1000 - pago 500 = 1500
    assert "SALDO A ABONAR: $ 1.500,00" in texto
    assert "Lu" in texto


def test_detalle_aislada_separa_reservas_posteriores(conn, profesional_aislada_con_edificios):
    id_prof, c1, _, _, _ = profesional_aislada_con_edificios
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=c1, Fecha="2026-09-03", HoraInicio=9, HoraFin=10,
        Estado="Confirmada", AplicaRecargo=0,
    )
    texto = mensaje_detalle_reserva_aislada(conn, id_profesional=id_prof, periodo="2026-08")
    assert "RESERVAS POSTERIORES:" in texto
    assert texto.index("RESERVAS POSTERIORES") > texto.index("SALDO A ABONAR")


def test_detalle_aislada_agrega_edificio_si_tiene_llaves_de_mas_de_uno(conn, profesional_aislada_con_edificios):
    id_prof, c1, c2, id_ed1, id_ed2 = profesional_aislada_con_edificios
    id_llave = obtener_repositorio(conn, "Llave").crear(Descripcion="Llave", ValorDepositoActual=5000)
    obtener_repositorio(conn, "LlaveAcceso").crear(IdLlave=id_llave, IdEdificio=id_ed1)
    obtener_repositorio(conn, "LlaveAcceso").crear(IdLlave=id_llave, IdEdificio=id_ed2)
    obtener_repositorio(conn, "LlaveProfesional").crear(IdLlave=id_llave, IdProfesional=id_prof, FechaEntrega="2026-08-02")
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=c1, Fecha="2026-08-05", HoraInicio=10, HoraFin=12,
        Estado="Confirmada", AplicaRecargo=0,
    )
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=c2, Fecha="2026-08-06", HoraInicio=10, HoraFin=12,
        Estado="Confirmada", AplicaRecargo=0,
    )
    texto = mensaje_detalle_reserva_aislada(
        conn, id_profesional=id_prof, periodo="2026-08", incluir_edificio=False,
    )
    assert "Ramos 1" in texto and "San Justo 1" in texto


def test_detalle_aislada_deposito_de_llave_del_mes(conn, profesional_aislada_con_edificios):
    id_prof, c1, _, id_ed1, _ = profesional_aislada_con_edificios
    id_llave = obtener_repositorio(conn, "Llave").crear(Descripcion="Llave", ValorDepositoActual=5000)
    obtener_repositorio(conn, "LlaveAcceso").crear(IdLlave=id_llave, IdEdificio=id_ed1)
    obtener_repositorio(conn, "LlaveProfesional").crear(
        IdLlave=id_llave, IdProfesional=id_prof, FechaEntrega="2026-08-02",
        DepositoCobrado=1, MontoCobrado=5000,
    )
    texto = mensaje_detalle_reserva_aislada(conn, id_profesional=id_prof, periodo="2026-08")
    assert "Depósito de llave: $ 5.000,00" in texto


# ------------------------------------- combinar misma/distintas unidades (5.1)

def test_detalle_aislada_sin_combinar_cada_reserva_en_su_propia_linea(conn, profesional_aislada_con_edificios):
    id_prof, c1, _, _, _ = profesional_aislada_con_edificios
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=c1, Fecha="2026-08-05", HoraInicio=10, HoraFin=12,
        Estado="Confirmada", AplicaRecargo=0,
    )
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=c1, Fecha="2026-08-05", HoraInicio=14, HoraFin=16,
        Estado="Confirmada", AplicaRecargo=0,
    )
    texto = mensaje_detalle_reserva_aislada(conn, id_profesional=id_prof, periodo="2026-08")
    assert "Miércoles 5/8 de 10 a 12hs" in texto
    assert "Miércoles 5/8 de 14 a 16hs" in texto
    assert "y de" not in texto


def test_detalle_aislada_combinar_misma_unidad_funde_horarios(conn, profesional_aislada_con_edificios):
    id_prof, c1, _, _, _ = profesional_aislada_con_edificios
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=c1, Fecha="2026-08-05", HoraInicio=10, HoraFin=12,
        Estado="Confirmada", AplicaRecargo=0,
    )
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=c1, Fecha="2026-08-05", HoraInicio=14, HoraFin=16,
        Estado="Confirmada", AplicaRecargo=0,
    )
    texto = mensaje_detalle_reserva_aislada(
        conn, id_profesional=id_prof, periodo="2026-08", combinar_misma_unidad=True,
    )
    assert "Miércoles 5/8 de 10 a 12hs y de 14 a 16hs" in texto
    assert "$ 2.000,00" in texto  # 4hs x 500 = 2000, una sola línea


def test_detalle_aislada_combinar_misma_unidad_no_funde_consultorios_distintos(conn, profesional_aislada_con_edificios):
    id_prof, c1, c2, _, _ = profesional_aislada_con_edificios
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=c1, Fecha="2026-08-05", HoraInicio=10, HoraFin=12,
        Estado="Confirmada", AplicaRecargo=0,
    )
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=c2, Fecha="2026-08-05", HoraInicio=14, HoraFin=16,
        Estado="Confirmada", AplicaRecargo=0,
    )
    texto = mensaje_detalle_reserva_aislada(
        conn, id_profesional=id_prof, periodo="2026-08", combinar_misma_unidad=True,
    )
    assert "Miércoles 5/8 de 10 a 12hs" in texto
    assert "Miércoles 5/8 de 14 a 16hs" in texto
    assert "y de" not in texto


def test_detalle_aislada_combinar_distintas_unidades_agrupa_bajo_la_fecha(conn, profesional_aislada_con_edificios):
    id_prof, c1, c2, _, _ = profesional_aislada_con_edificios
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=c1, Fecha="2026-08-05", HoraInicio=10, HoraFin=12,
        Estado="Confirmada", AplicaRecargo=0,
    )
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=c2, Fecha="2026-08-05", HoraInicio=14, HoraFin=15,
        Estado="Confirmada", AplicaRecargo=0,
    )
    texto = mensaje_detalle_reserva_aislada(
        conn, id_profesional=id_prof, periodo="2026-08", combinar_distintas_unidades=True,
    )
    # c1: 2hs x 500 = 1000; c2: 1hs x 600 = 600; total del día = 1600
    assert "Miércoles 5/8: $ 1.600,00" in texto
    assert "de 10 a 12hs - consul 1" in texto
    assert "de 14 a 15hs - consul 2" in texto


def test_detalle_aislada_combinar_distintas_unidades_implica_combinar_misma_unidad(
    conn, profesional_aislada_con_edificios,
):
    id_prof, c1, _, _, _ = profesional_aislada_con_edificios
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=c1, Fecha="2026-08-05", HoraInicio=10, HoraFin=12,
        Estado="Confirmada", AplicaRecargo=0,
    )
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=c1, Fecha="2026-08-05", HoraInicio=14, HoraFin=16,
        Estado="Confirmada", AplicaRecargo=0,
    )
    texto = mensaje_detalle_reserva_aislada(
        conn, id_profesional=id_prof, periodo="2026-08", combinar_distintas_unidades=True,
    )
    # un solo consultorio ese día -> no hay encabezado de día, pero sigue fundiendo los horarios
    assert "Miércoles 5/8 de 10 a 12hs y de 14 a 16hs" in texto
    assert "Miércoles 5/8: " not in texto


def test_detalle_aislada_combinar_no_afecta_reservas_de_dias_distintos(conn, profesional_aislada_con_edificios):
    id_prof, c1, _, _, _ = profesional_aislada_con_edificios
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=c1, Fecha="2026-08-05", HoraInicio=10, HoraFin=12,
        Estado="Confirmada", AplicaRecargo=0,
    )
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=c1, Fecha="2026-08-06", HoraInicio=10, HoraFin=12,
        Estado="Confirmada", AplicaRecargo=0,
    )
    texto = mensaje_detalle_reserva_aislada(
        conn, id_profesional=id_prof, periodo="2026-08",
        combinar_misma_unidad=True, combinar_distintas_unidades=True,
    )
    assert "Miércoles 5/8 de 10 a 12hs" in texto
    assert "Jueves 6/8 de 10 a 12hs" in texto
    assert "y de" not in texto


@pytest.fixture
def edificio_dos_consultorios(conn):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='7mo "L"')
    c1 = obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=1, Ventana=1, ValorHoraRegularActual=1000,
    )
    c2 = obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=2, Ventana=0, ValorHoraRegularActual=1000,
    )
    return c1, c2


def test_disponibilidad_horarios_sin_coincidencia(conn, edificio_dos_consultorios):
    c1, c2 = edificio_dos_consultorios
    otro = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Otro")
    for c in (c1, c2):
        obtener_repositorio(conn, "ReservaRegular").crear(
            IdProfesional=otro, IdConsultorio=c, DiaSemana="Lunes", HoraInicio=10, HoraFin=12,
            VigenciaInicio="2026-01-01",
        )
    texto = mensaje_disponibilidad_horarios(conn, periodo="2026-08", dias=["Lunes"], horario_desde=10, horario_hasta=12)
    assert "Sin disponibilidad para lo solicitado." in texto


def test_disponibilidad_horarios_alternativa_simple(conn, edificio_dos_consultorios):
    texto = mensaje_disponibilidad_horarios(conn, periodo="2026-08", dias=["Lunes"], horario_desde=10, horario_hasta=12)
    assert "Alternativas disponibles:" in texto
    assert "· Lunes de 10 a 12hs" in texto


def test_disponibilidad_horarios_combinacion_indentada(conn, edificio_dos_consultorios):
    c1, c2 = edificio_dos_consultorios
    otro = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Otro")
    # c1 libre 10-11, c2 libre 11-12: hace falta combinar para cubrir 10-12
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=otro, IdConsultorio=c1, DiaSemana="Lunes", HoraInicio=11, HoraFin=12, VigenciaInicio="2026-01-01",
    )
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=otro, IdConsultorio=c2, DiaSemana="Lunes", HoraInicio=10, HoraFin=11, VigenciaInicio="2026-01-01",
    )
    texto = mensaje_disponibilidad_horarios(conn, periodo="2026-08", dias=["Lunes"], horario_desde=10, horario_hasta=12)
    assert "· Lunes:" in texto
    lineas = texto.splitlines()
    idx = lineas.index("· Lunes:")
    assert lineas[idx + 1].startswith("  - ")
    assert lineas[idx + 2].startswith("  - ")


def test_disponibilidad_horarios_muestra_caracteristicas_pedidas(conn, edificio_dos_consultorios):
    texto = mensaje_disponibilidad_horarios(
        conn, periodo="2026-08", dias=["Lunes"], horario_desde=10, horario_hasta=11,
        condiciones_consultorio={"ventana": True},
    )
    assert "Características: con ventana" in texto


def test_sustituir_variables_respeta_saltos_de_linea():
    texto = "Hola {nombre},\nTu saldo es {saldo}."
    resultado = sustituir_variables(texto, {"nombre": "Ana", "saldo": "$1000"})
    assert resultado == "Hola Ana,\nTu saldo es $1000."


def test_sustituir_variables_deja_variables_no_provistas_intactas():
    resultado = sustituir_variables("Hola {nombre}, {otra}", {"nombre": "Ana"})
    assert resultado == "Hola Ana, {otra}"


def test_dias_desde_ultimo_pago_nunca_pago_devuelve_none(conn, consultorio):
    id_prof = _crear_regular(conn, consultorio)
    assert dias_desde_ultimo_pago(conn, id_prof, date(2026, 8, 15)) is None


def test_dias_desde_ultimo_pago_usa_el_mas_reciente(conn, consultorio):
    id_prof = _crear_regular(conn, consultorio)
    obtener_repositorio(conn, "HistorialPagos").crear(IdProfesional=id_prof, Fecha="2026-08-01", Monto=100)
    obtener_repositorio(conn, "HistorialPagos").crear(IdProfesional=id_prof, Fecha="2026-08-10", Monto=100)
    assert dias_desde_ultimo_pago(conn, id_prof, date(2026, 8, 15)) == 5


def test_dias_desde_ultimo_pago_ignora_ajustes(conn, consultorio):
    id_prof = _crear_regular(conn, consultorio)
    obtener_repositorio(conn, "HistorialPagos").crear(IdProfesional=id_prof, Fecha="2026-08-01", Monto=100)
    obtener_repositorio(conn, "HistorialPagos").crear(
        IdProfesional=id_prof, Fecha="2026-08-14", Monto=30, EsAjuste=1,
    )
    assert dias_desde_ultimo_pago(conn, id_prof, date(2026, 8, 15)) == 14


def test_plan_activo_devuelve_none_sin_plan(conn, consultorio):
    id_prof = _crear_regular(conn, consultorio)
    assert plan_activo(conn, id_prof) is None


def test_plan_activo_devuelve_el_plan_activo(conn, consultorio):
    id_prof = _crear_regular(conn, consultorio)
    id_plan = crear_plan_pago(
        conn, id_profesional=id_prof, monto_refinanciado=1000, porcentaje_interes_mensual=0,
        cantidad_cuotas=2, mes_ano_inicio=PERIODO,
    )
    plan = plan_activo(conn, id_prof)
    assert plan is not None
    assert plan["IdPlan"] == id_plan
