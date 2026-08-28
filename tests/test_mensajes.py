from datetime import date

import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.mensajes import (
    _lista_con_y,
    dias_desde_ultimo_pago,
    mensaje_detalle_reserva_aislada,
    mensaje_disponibilidad_horarios,
    mensaje_disponibilidad_horarios_fecha,
    mensaje_envio_liquidacion,
    mensaje_grupal,
    mensaje_situacion_1,
    mensaje_situacion_2,
    mensaje_situacion_3,
    mensaje_situacion_4,
    mensaje_situacion_5,
    nombre_para_mensaje,
    plan_activo,
    sustituir_variables,
)
from app.negocio.pagos import crear_cargo_especial, crear_plan_pago_historico, registrar_pago
from app.repositorio.registro import obtener_repositorio

PERIODO = "2026-08"
HOY = date(2026, 8, 15)


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


# ------------------------------------------------------------- situaciones (DC-02 §5 / DC-03)

def test_mensaje_situacion_1_incluye_saldo_y_fecha_remanente(conn, consultorio):
    id_prof = _crear_regular(conn, consultorio, SaldoCuentaAnterior=50000)
    texto = mensaje_situacion_1(conn, id_prof, HOY)
    assert "$50.000" in texto
    assert "MENSAJE AUTOMATICO" in texto


def test_mensaje_situacion_1_rechaza_categoria_no_r(conn):
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="A", Apellido="Aislada")
    with pytest.raises(ValueError):
        mensaje_situacion_1(conn, id_prof, HOY)


def test_mensaje_situacion_2_incluye_nombre_y_mes(conn, consultorio):
    id_prof = _crear_regular(conn, consultorio, Apodo="Male")
    texto = mensaje_situacion_2(conn, id_prof, PERIODO)
    assert "Male" in texto
    assert "agosto" in texto


def test_mensaje_situacion_3_incluye_saldo_y_cuando(conn, consultorio):
    id_prof = _crear_regular(conn, consultorio, Apodo="Male", SaldoCuentaAnterior=1234)
    texto = mensaje_situacion_3(conn, id_prof, PERIODO, HOY)
    assert "Male" in texto
    assert "$1.234" in texto


def test_mensaje_situacion_4_incluye_saldo_mes_en_curso(conn, consultorio):
    id_prof = _crear_regular(conn, consultorio, Apodo="Male", SaldoCuentaActual=5000)
    texto = mensaje_situacion_4(conn, id_prof)
    assert "Male" in texto
    assert "$5.000" in texto


def test_mensaje_situacion_5_incluye_saldo_anterior(conn, consultorio):
    id_prof = _crear_regular(conn, consultorio, Apodo="Male", SaldoCuentaAnterior=8500)
    texto = mensaje_situacion_5(conn, id_prof, PERIODO)
    assert "Male" in texto
    assert "$8.500" in texto


def test_mensaje_envio_liquidacion_menciona_el_mes(conn, consultorio):
    id_prof = _crear_regular(conn, consultorio)
    texto = mensaje_envio_liquidacion(conn, id_prof, PERIODO)
    assert "agosto" in texto
    assert "MENSAJE AUTOMATICO" in texto


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
    assert "al lunes 7/9 por ser feriado nacional" in texto


def test_mensaje_grupal_con_varios_feriados_concuerda_en_plural(conn):
    obtener_repositorio(conn, "FechasEspeciales").crear(Fecha="2026-09-07", Tipo="Feriado nacional")
    obtener_repositorio(conn, "FechasEspeciales").crear(Fecha="2026-09-21", Tipo="Día no laborable")
    texto = mensaje_grupal(conn, PERIODO)
    assert "esos días" in texto
    assert " y " in texto


# ------------------------------------------------------------- Mensaje 1: detalle de aisladas (DC-03)

@pytest.fixture
def profesional_aislada_con_edificios(conn):
    id_ed1 = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1", Domicilio="Av. Rivadavia 1234", DomicilioLocalidad="CABA")
    id_ed2 = obtener_repositorio(conn, "Edificio").crear(Nombre="San Justo 1", Domicilio="Belgrano 500", DomicilioLocalidad="San Justo")
    id_un1 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_ed1, Departamento='7mo "L"')
    id_un2 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_ed2, Departamento='3ro "B"')
    c1 = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_un1, NumeroConsultorio=1, ValorHoraAisladaActual=500)
    c2 = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_un2, NumeroConsultorio=2, ValorHoraAisladaActual=600)
    id_prof = obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="A", Apellido="Aislada", Apodo="Lu", Tratamiento="Lic.", NombrePila="Lucia",
        SaldoCuentaAnterior=1000,
    )
    return id_prof, c1, c2, id_ed1, id_ed2


def test_detalle_aislada_encabezado_en_mayusculas(conn, profesional_aislada_con_edificios):
    id_prof, _, _, _, _ = profesional_aislada_con_edificios
    texto = mensaje_detalle_reserva_aislada(conn, id_profesional=id_prof, periodo="2026-08")
    lineas = texto.splitlines()
    assert lineas[0] == "DETALLE RESERVA AGOSTO"
    assert lineas[1] == "LIC. LUCIA AISLADA"
    assert lineas[2] == ""


def test_detalle_aislada_calcula_saldo_a_abonar(conn, profesional_aislada_con_edificios):
    id_prof, c1, c2, _, _ = profesional_aislada_con_edificios
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=c1, Fecha="2026-08-05", HoraInicio=10, HoraFin=12,
        Estado="Confirmada", AplicaRecargo=0,
    )
    registrar_pago(conn, id_profesional=id_prof, monto=500, fecha="2026-08-15", periodo_imputado="2026-08")

    texto = mensaje_detalle_reserva_aislada(conn, id_profesional=id_prof, periodo="2026-08")
    # saldo_anterior 1000 + reserva (2hs x 500) 1000 - pago 500 = 1500
    assert "SALDO A ABONAR: $1.500" in texto
    assert "+ Saldo pendiente mes anterior $1.000" in texto
    assert "- Pagos registrados en mes en curso $500" in texto


def test_detalle_aislada_de_reubicacion_no_genera_cargo(conn, profesional_aislada_con_edificios):
    id_prof, c1, _, _, _ = profesional_aislada_con_edificios
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=c1, Fecha="2026-08-05", HoraInicio=10, HoraFin=12,
        Estado="Confirmada", AplicaRecargo=1, EsReubicacion=1,
    )
    texto = mensaje_detalle_reserva_aislada(conn, id_profesional=id_prof, periodo="2026-08")
    # saldo_anterior 1000 sin cargo adicional por la reubicación
    assert "SALDO A ABONAR: $1.000" in texto


def test_detalle_aislada_omite_saldo_anterior_si_es_cero(conn, profesional_aislada_con_edificios):
    id_prof, c1, _, _, _ = profesional_aislada_con_edificios
    obtener_repositorio(conn, "Profesional").actualizar(id_prof, SaldoCuentaAnterior=0)
    texto = mensaje_detalle_reserva_aislada(conn, id_profesional=id_prof, periodo="2026-08")
    assert "Saldo pendiente mes anterior" not in texto
    assert "Saldo a favor mes anterior" not in texto


def test_detalle_aislada_saldo_a_favor_se_muestra_negativo(conn, profesional_aislada_con_edificios):
    id_prof, _, _, _, _ = profesional_aislada_con_edificios
    obtener_repositorio(conn, "Profesional").actualizar(id_prof, SaldoCuentaAnterior=-300)
    texto = mensaje_detalle_reserva_aislada(conn, id_profesional=id_prof, periodo="2026-08")
    assert "- Saldo a favor mes anterior $300" in texto


def test_detalle_aislada_separa_reservas_posteriores_sin_dos_puntos(conn, profesional_aislada_con_edificios):
    id_prof, c1, _, _, _ = profesional_aislada_con_edificios
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=c1, Fecha="2026-09-03", HoraInicio=9, HoraFin=10,
        Estado="Confirmada", AplicaRecargo=0,
    )
    texto = mensaje_detalle_reserva_aislada(conn, id_profesional=id_prof, periodo="2026-08")
    lineas = texto.splitlines()
    assert "RESERVAS POSTERIORES" in lineas
    assert texto.index("RESERVAS POSTERIORES") > texto.index("SALDO A ABONAR")


def test_detalle_aislada_un_solo_edificio_en_el_espacio_nunca_lo_menciona(conn):
    """Regla del edificio, primer nivel: con un solo edificio en todo el
    espacio se omite siempre, aunque el control esté tildado."""
    id_ed = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1", Domicilio="Rivadavia 1", DomicilioLocalidad="CABA")
    id_un = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_ed, Departamento='7mo "L"')
    c1 = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_un, NumeroConsultorio=1, ValorHoraAisladaActual=500)
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="A", Apellido="Aislada")
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=c1, Fecha="2026-08-05", HoraInicio=10, HoraFin=12,
        Estado="Confirmada", AplicaRecargo=0,
    )
    texto = mensaje_detalle_reserva_aislada(conn, id_profesional=id_prof, periodo="2026-08", incluir_edificio=True)
    assert "Edificio" not in texto


def test_detalle_aislada_omite_edificio_si_las_llaves_son_de_uno_solo(conn, profesional_aislada_con_edificios):
    id_prof, c1, c2, id_ed1, _ = profesional_aislada_con_edificios
    id_llave = obtener_repositorio(conn, "Llave").crear(Descripcion="Llave", Tipo="Unidad", ValorDepositoActual=5000)
    obtener_repositorio(conn, "LlaveAcceso").crear(IdLlave=id_llave, IdEdificio=id_ed1)
    obtener_repositorio(conn, "LlaveProfesional").crear(IdLlave=id_llave, IdProfesional=id_prof, FechaEntrega="2026-07-02")
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=c1, Fecha="2026-08-05", HoraInicio=10, HoraFin=12,
        Estado="Confirmada", AplicaRecargo=0,
    )
    texto = mensaje_detalle_reserva_aislada(conn, id_profesional=id_prof, periodo="2026-08")
    assert "Edificio" not in texto


def test_detalle_aislada_sin_llaves_pero_con_mas_de_un_edificio_lo_menciona(conn, profesional_aislada_con_edificios):
    """Un profesional sin ninguna llave todavía (recién empieza, alguien
    más le abre la puerta la primera vez) igual necesita saber en qué
    edificio es si el espacio tiene más de uno — confirmado por el
    usuario, corrige el supuesto anterior de omitirlo en este caso."""
    id_prof, c1, _, _, _ = profesional_aislada_con_edificios
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=c1, Fecha="2026-08-05", HoraInicio=10, HoraFin=12,
        Estado="Confirmada", AplicaRecargo=0,
    )
    texto = mensaje_detalle_reserva_aislada(conn, id_profesional=id_prof, periodo="2026-08")
    assert "Edificio Ramos 1" in texto


def test_detalle_aislada_agrega_edificio_si_tiene_llaves_de_mas_de_uno(conn, profesional_aislada_con_edificios):
    id_prof, c1, c2, id_ed1, id_ed2 = profesional_aislada_con_edificios
    id_llave = obtener_repositorio(conn, "Llave").crear(Descripcion="Llave", Tipo="Unidad", ValorDepositoActual=5000)
    obtener_repositorio(conn, "LlaveAcceso").crear(IdLlave=id_llave, IdEdificio=id_ed1)
    obtener_repositorio(conn, "LlaveAcceso").crear(IdLlave=id_llave, IdEdificio=id_ed2)
    obtener_repositorio(conn, "LlaveProfesional").crear(IdLlave=id_llave, IdProfesional=id_prof, FechaEntrega="2026-07-02")
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
    assert "Edificio Ramos 1" in texto and "Edificio San Justo 1" in texto


def test_detalle_aislada_deposito_de_llave_del_mes(conn, profesional_aislada_con_edificios):
    id_prof, c1, _, id_ed1, _ = profesional_aislada_con_edificios
    id_llave = obtener_repositorio(conn, "Llave").crear(Descripcion="Llave", Tipo="Unidad", ValorDepositoActual=5000)
    obtener_repositorio(conn, "LlaveAcceso").crear(IdLlave=id_llave, IdEdificio=id_ed1, IdUnidad=None)
    obtener_repositorio(conn, "LlaveProfesional").crear(
        IdLlave=id_llave, IdProfesional=id_prof, FechaEntrega="2026-08-02",
        DepositoCobrado=1, MontoCobrado=5000,
    )
    texto = mensaje_detalle_reserva_aislada(conn, id_profesional=id_prof, periodo="2026-08")
    assert "+ Depósito por llave unidad $5.000" in texto


def test_detalle_aislada_reintegro_de_llave_se_muestra_negativo(conn, profesional_aislada_con_edificios):
    id_prof, _, _, id_ed1, _ = profesional_aislada_con_edificios
    id_llave = obtener_repositorio(conn, "Llave").crear(Descripcion="Llave", Tipo="Unidad", ValorDepositoActual=5000)
    obtener_repositorio(conn, "LlaveAcceso").crear(IdLlave=id_llave, IdEdificio=id_ed1, IdUnidad=None)
    obtener_repositorio(conn, "LlaveProfesional").crear(
        IdLlave=id_llave, IdProfesional=id_prof, FechaEntrega="2026-07-01", FechaDevolucion="2026-08-02",
        DepositoCobrado=1, MontoCobrado=5000, DepositoReintegrado=1, MontoReintegrado=5000,
    )
    # ya devuelta al momento de generar el mensaje -> no cuenta como llave "en
    # poder" del profesional, así que la regla del edificio no la suprime.
    texto = mensaje_detalle_reserva_aislada(conn, id_profesional=id_prof, periodo="2026-08")
    assert "- Reintegro depósito llave unidad - Edificio Ramos 1 -$5.000" in texto


def test_detalle_aislada_item_libre_debito_y_credito(conn, profesional_aislada_con_edificios):
    id_prof, _, _, _, _ = profesional_aislada_con_edificios
    crear_cargo_especial(conn, id_profesional=id_prof, tipo="Débito", concepto="ajuste manual", monto=200, periodo_imputado="2026-08")
    crear_cargo_especial(conn, id_profesional=id_prof, tipo="Crédito", concepto="bonificación", monto=-100, periodo_imputado="2026-08")
    texto = mensaje_detalle_reserva_aislada(conn, id_profesional=id_prof, periodo="2026-08")
    assert "+ Ajuste manual $200" in texto
    assert "- Bonificación $100" in texto


def test_detalle_aislada_item_libre_no_incluye_cargos_de_llave(conn, profesional_aislada_con_edificios):
    """Los CargoEspecial ligados a IdLlave (depósito/reintegro) no se
    listan de nuevo como ítem libre — ya se muestran vía LlaveProfesional."""
    id_prof, _, _, id_ed1, _ = profesional_aislada_con_edificios
    id_llave = obtener_repositorio(conn, "Llave").crear(Descripcion="Llave", Tipo="Unidad", ValorDepositoActual=5000)
    crear_cargo_especial(
        conn, id_profesional=id_prof, tipo="Débito", concepto="depósito llave", monto=5000,
        periodo_imputado="2026-08", id_llave=id_llave,
    )
    texto = mensaje_detalle_reserva_aislada(conn, id_profesional=id_prof, periodo="2026-08")
    assert "depósito llave" not in texto.lower().replace("depósito por llave", "")


def test_detalle_aislada_nota_de_sobres_solo_si_hubo_pago_por_sobre(conn, profesional_aislada_con_edificios):
    id_prof, _, _, _, _ = profesional_aislada_con_edificios
    registrar_pago(
        conn, id_profesional=id_prof, monto=500, fecha="2026-08-15", periodo_imputado="2026-08",
        medio_pago="Sobre en buzón",
    )
    ultimo = obtener_repositorio(conn, "HistorialPagos").listar(IdProfesional=id_prof)[-1]
    obtener_repositorio(conn, "HistorialPagos").actualizar(ultimo["IdPago"], FechaHoraRecogidaSobres="2026-08-18T15:00:00")
    texto = mensaje_detalle_reserva_aislada(conn, id_profesional=id_prof, periodo="2026-08")
    assert "* Nota: Se imputaron los pagos de los sobres recogidos en las unidades hasta el martes 18/8 a las 15hs." in texto


def test_detalle_aislada_sin_nota_de_sobres_si_no_hubo_pago_por_sobre(conn, profesional_aislada_con_edificios):
    id_prof, _, _, _, _ = profesional_aislada_con_edificios
    registrar_pago(conn, id_profesional=id_prof, monto=500, fecha="2026-08-15", periodo_imputado="2026-08")
    texto = mensaje_detalle_reserva_aislada(conn, id_profesional=id_prof, periodo="2026-08")
    assert "Nota:" not in texto


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
    assert "$2.000" in texto  # 4hs x 500 = 2000, una sola línea


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
    assert "Miércoles 5/8: $1.600" in texto
    assert "de 10 a 12hs consul 1" in texto
    assert "de 14 a 15hs consul 2" in texto


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


# ------------------------------------------------------------- Mensaje 2: disponibilidad (DC-03)

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


def test_disponibilidad_horarios_omite_edificio_unico(conn, edificio_dos_consultorios):
    """Regla del edificio: un solo edificio en el espacio -> nunca se menciona,
    ni siquiera con el control tildado."""
    texto = mensaje_disponibilidad_horarios(
        conn, periodo="2026-08", dias=["Lunes"], horario_desde=10, horario_hasta=12, incluir_edificio=True,
    )
    assert "Edificio" not in texto


# --------------------------------------------------- Mensaje 2 Variante B: fecha puntual (DC-03)

def test_disponibilidad_fecha_alternativa_simple(conn, edificio_dos_consultorios):
    texto, advertencias = mensaje_disponibilidad_horarios_fecha(
        conn, fechas=["2026-08-03"], horario_desde=10, horario_hasta=12,  # lunes
    )
    assert "Alternativas disponibles:" in texto
    assert "· lunes 3/8 de 10 a 12hs" in texto
    assert advertencias == []


def test_disponibilidad_fecha_sin_coincidencia(conn, edificio_dos_consultorios):
    c1, c2 = edificio_dos_consultorios
    otro = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Otro")
    for c in (c1, c2):
        obtener_repositorio(conn, "ReservaRegular").crear(
            IdProfesional=otro, IdConsultorio=c, DiaSemana="Lunes", HoraInicio=10, HoraFin=12,
            VigenciaInicio="2026-01-01",
        )
    texto, _advertencias = mensaje_disponibilidad_horarios_fecha(
        conn, fechas=["2026-08-03"], horario_desde=10, horario_hasta=12,
    )
    assert "Sin disponibilidad para lo solicitado." in texto


def test_disponibilidad_fecha_respeta_ausencia_puntual(conn, edificio_dos_consultorios):
    """La ventaja de la Variante B sobre la A: una ausencia puntual libera
    el consultorio para esa fecha exacta, aunque el patrón semanal genérico
    lo muestre ocupado."""
    c1, c2 = edificio_dos_consultorios
    otro = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Otro")
    for c in (c1, c2):
        obtener_repositorio(conn, "ReservaRegular").crear(
            IdProfesional=otro, IdConsultorio=c, DiaSemana="Lunes", HoraInicio=10, HoraFin=12,
            VigenciaInicio="2026-01-01",
        )
    from app.negocio.ausencias import crear_ausencia
    crear_ausencia(conn, id_profesional=otro, fecha_desde="2026-08-03", fecha_hasta="2026-08-03")

    texto, _advertencias = mensaje_disponibilidad_horarios_fecha(
        conn, fechas=["2026-08-03"], horario_desde=10, horario_hasta=12,
    )
    assert "Alternativas disponibles:" in texto


def test_disponibilidad_fecha_varias_fechas_en_el_encabezado(conn, edificio_dos_consultorios):
    texto, _advertencias = mensaje_disponibilidad_horarios_fecha(
        conn, fechas=["2026-08-03", "2026-08-10"], horario_desde=10, horario_hasta=11,
    )
    assert "lunes 3/8" in texto
    assert "lunes 10/8" in texto


def test_disponibilidad_fecha_aislada_no_bloquea_pero_avisa_para_el_operador(conn, edificio_dos_consultorios):
    """La aislada NO aparece en el texto del mensaje (eso es para el
    profesional, no le interesa la agenda de otro) — solo en las
    advertencias, que son de uso interno."""
    c1, _c2 = edificio_dos_consultorios
    id_prof_aislada = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="A", Apellido="Puntual")
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof_aislada, IdConsultorio=c1, Fecha="2026-08-03",
        HoraInicio=10, HoraFin=12, Estado="Confirmada",
    )

    texto, advertencias = mensaje_disponibilidad_horarios_fecha(
        conn, fechas=["2026-08-03"], horario_desde=10, horario_hasta=12,
    )
    assert "Alternativas disponibles:" in texto
    assert "Puntual" not in texto
    assert len(advertencias) == 1
    assert "Puntual" in advertencias[0]


# ------------------------------------------------------------- utilitarios

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
    id_plan = crear_plan_pago_historico(
        conn, id_profesional=id_prof, monto_refinanciado=1000, porcentaje_interes_mensual=0,
        cantidad_cuotas=2, mes_ano_inicio=PERIODO,
    )
    plan = plan_activo(conn, id_prof)
    assert plan is not None
    assert plan["IdPlan"] == id_plan
