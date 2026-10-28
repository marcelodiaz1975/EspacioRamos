from datetime import date

import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.mensajes import (
    _lista_con_y,
    dias_desde_ultimo_pago,
    mensaje_detalle_reserva_aislada,
    mensaje_envio_liquidacion,
    mensaje_grupal,
    mensaje_recordatorio_deuda_profesional_x,
    mensaje_recordatorio_fin_de_mes,
    mensaje_situacion_1,
    mensaje_situacion_2,
    mensaje_situacion_3,
    mensaje_situacion_5,
    nombre_para_mensaje,
    plan_activo,
    sustituir_variables,
)
from app.negocio.pagos import crear_cargo_especial, crear_plan_pago_historico, registrar_pago
from app.negocio.placas import asignar_placa
from app.repositorio.registro import obtener_repositorio

PERIODO = "2026-08"
HOY = date(2026, 8, 15)


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    # Mismo "hoy" que HOY/PERIODO de arriba — varios tests pasan por
    # registrar_pago/crear_cargo_especial, que validan periodo_imputado
    # contra la fecha REAL del sistema si no se fija la fecha ficticia
    # (sin esto, los tests quedan atados al mes en que se escribieron).
    connection.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-08-15' WHERE IdConfiguracion = 1"
    )
    connection.commit()
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


# ------------------------------- recordatorio de deuda a profesionales categoría X

def test_mensaje_recordatorio_deuda_profesional_x_incluye_saldo_y_nombre_del_espacio(conn):
    id_prof = obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="X", Apellido="DejoElEspacio", SaldoCuentaAnterior=5000,
    )
    conn.execute("UPDATE Configuracion SET NombreEspacio = 'Espacio Ramos' WHERE IdConfiguracion = 1")
    conn.commit()
    texto = mensaje_recordatorio_deuda_profesional_x(conn, id_prof)
    assert "$5.000" in texto
    assert "MENSAJE AUTOMATICO" in texto
    assert "Espacio Ramos" in texto


def test_mensaje_recordatorio_deuda_profesional_x_rechaza_categoria_no_x(conn, consultorio):
    id_prof = _crear_regular(conn, consultorio, SaldoCuentaAnterior=5000)
    with pytest.raises(ValueError):
        mensaje_recordatorio_deuda_profesional_x(conn, id_prof)


# ------------------------------------------------- recordatorio de fin de mes (bordó)

def test_recordatorio_fin_de_mes_saldo_en_cero(conn, consultorio):
    id_prof = _crear_regular(conn, consultorio, SaldoCuentaActual=0)
    texto = mensaje_recordatorio_fin_de_mes(conn, id_prof, PERIODO)
    assert "MENSAJE AUTOMATICO" in texto
    assert "Saldo en cero, sin deuda." in texto
    assert "A favor del profesional" not in texto
    assert "Pendiente de cancelación" not in texto


def test_recordatorio_fin_de_mes_saldo_a_favor_del_profesional(conn, consultorio):
    id_prof = _crear_regular(conn, consultorio, SaldoCuentaActual=-4586)
    texto = mensaje_recordatorio_fin_de_mes(conn, id_prof, PERIODO)
    assert "A favor del profesional $4.586." in texto


def test_recordatorio_fin_de_mes_saldo_pendiente_sin_fecha_de_sobres(conn, consultorio):
    id_prof = _crear_regular(conn, consultorio, SaldoCuentaActual=4586)
    texto = mensaje_recordatorio_fin_de_mes(conn, id_prof, PERIODO)
    assert "Pendiente de cancelación $4.586." in texto
    assert "sobres" not in texto


def test_recordatorio_fin_de_mes_saldo_pendiente_con_fecha_de_sobres(conn, consultorio):
    id_prof = _crear_regular(conn, consultorio, SaldoCuentaActual=4586)
    obtener_repositorio(conn, "Configuracion").actualizar(1, FechaHoraRecogidaSobres="2026-08-25T16:00:00")
    texto = mensaje_recordatorio_fin_de_mes(conn, id_prof, PERIODO)
    assert "hasta las 16hs del martes 25/8." in texto


def test_recordatorio_fin_de_mes_cierre_de_reservas_y_envio_de_liquidaciones(conn, consultorio):
    id_prof = _crear_regular(conn, consultorio, SaldoCuentaActual=0)
    texto = mensaje_recordatorio_fin_de_mes(conn, id_prof, PERIODO)
    assert "CIERRE DE RESERVAS" in texto
    assert "* lunes 31/8" in texto.lower()
    assert "ENVIO DE LIQUIDACIONES" in texto
    assert "* martes 1/9" in texto.lower()


def test_recordatorio_fin_de_mes_sin_feriados_no_muestra_la_seccion(conn, consultorio):
    id_prof = _crear_regular(conn, consultorio, SaldoCuentaActual=0)
    texto = mensaje_recordatorio_fin_de_mes(conn, id_prof, PERIODO)
    assert "FERIADOS" not in texto


def test_recordatorio_fin_de_mes_con_feriados_los_lista_uno_por_uno(conn, consultorio):
    id_prof = _crear_regular(conn, consultorio, SaldoCuentaActual=0)
    obtener_repositorio(conn, "FechasEspeciales").crear(Fecha="2026-09-07", Tipo="Feriado nacional")
    obtener_repositorio(conn, "FechasEspeciales").crear(Fecha="2026-09-21", Tipo="Día no laborable")
    texto = mensaje_recordatorio_fin_de_mes(conn, id_prof, PERIODO)
    assert "PROXIMOS FERIADOS" in texto
    assert "* Lunes 7/9" in texto
    assert "* Lunes 21/9" in texto


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
    id_caba = obtener_repositorio(conn, "Localidad").crear(Localidad="CABA")
    id_san_justo = obtener_repositorio(conn, "Localidad").crear(Localidad="San Justo")
    id_ed1 = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1", Domicilio="Av. Rivadavia 1234", IdLocalidad=id_caba)
    id_ed2 = obtener_repositorio(conn, "Edificio").crear(Nombre="San Justo 1", Domicilio="Belgrano 500", IdLocalidad=id_san_justo)
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


def test_detalle_aislada_extraordinaria_usa_el_monto_manual_y_el_item_de_texto_libre(
    conn, profesional_aislada_con_edificios,
):
    id_prof, c1, _, _, _ = profesional_aislada_con_edificios
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=c1, Fecha="2026-08-05", HoraInicio=10, HoraFin=12,
        Estado="Confirmada", AplicaRecargo=0, EsExtraordinaria=1,
        ItemExtraordinario="Uso del consultorio para un taller puntual", MontoExtraordinario=12000,
    )
    texto = mensaje_detalle_reserva_aislada(conn, id_profesional=id_prof, periodo="2026-08")
    # saldo_anterior 1000 + extraordinaria 12000 = 13000 (no 2hs x 500 = 1000)
    assert "SALDO A ABONAR: $13.000" in texto
    assert "Uso del consultorio para un taller puntual $12.000" in texto


def test_detalle_aislada_extraordinaria_incluye_horario_y_consultorio(conn, profesional_aislada_con_edificios):
    """Pedido explícito de la clienta: el texto de una extraordinaria
    tiene que incluir horario y consultorio/unidad, igual que el de
    cualquier aislada común — antes solo mostraba día, fecha, ítem y
    monto, sin decir CUÁNDO ni DÓNDE."""
    id_prof, c1, _, _, _ = profesional_aislada_con_edificios
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=c1, Fecha="2026-08-05", HoraInicio=10, HoraFin=12,
        Estado="Confirmada", AplicaRecargo=0, EsExtraordinaria=1,
        ItemExtraordinario="Uso del consultorio para un taller puntual", MontoExtraordinario=12000,
    )
    texto = mensaje_detalle_reserva_aislada(conn, id_profesional=id_prof, periodo="2026-08")
    assert "de 10 a 12hs" in texto
    assert "consul 1" in texto
    assert "Uso del consultorio para un taller puntual $12.000" in texto


def test_detalle_aislada_extraordinaria_y_normal_conviven_en_el_mismo_mes(conn, profesional_aislada_con_edificios):
    id_prof, c1, _, _, _ = profesional_aislada_con_edificios
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=c1, Fecha="2026-08-05", HoraInicio=10, HoraFin=12,
        Estado="Confirmada", AplicaRecargo=0,
    )
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=c1, Fecha="2026-08-12", HoraInicio=9, HoraFin=10,
        Estado="Confirmada", AplicaRecargo=0, EsExtraordinaria=1,
        ItemExtraordinario="Taller puntual", MontoExtraordinario=3000,
    )
    texto = mensaje_detalle_reserva_aislada(conn, id_profesional=id_prof, periodo="2026-08")
    # saldo_anterior 1000 + aislada normal (2hs x 500) 1000 + extraordinaria 3000 = 5000
    assert "SALDO A ABONAR: $5.000" in texto
    assert "Taller puntual $3.000" in texto


def test_detalle_aislada_extraordinaria_posterior_va_en_su_propia_seccion(conn, profesional_aislada_con_edificios):
    id_prof, c1, _, _, _ = profesional_aislada_con_edificios
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=c1, Fecha="2026-09-05", HoraInicio=10, HoraFin=12,
        Estado="Confirmada", AplicaRecargo=0, EsExtraordinaria=1,
        ItemExtraordinario="Taller de septiembre", MontoExtraordinario=4000,
    )
    texto = mensaje_detalle_reserva_aislada(conn, id_profesional=id_prof, periodo="2026-08")
    assert "RESERVAS POSTERIORES" in texto
    assert "Taller de septiembre $4.000" in texto
    # no se suma al saldo de agosto, todavía no corresponde a este período
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


def test_detalle_aislada_un_solo_edificio_en_el_mensaje_no_repite_la_mencion(conn):
    """Regla propia de este mensaje (no la "regla del edificio" general
    del sistema, ligada a llaves): con un solo edificio INVOLUCRADO EN
    EL MENSAJE se agrega la dirección una vez arriba de todo, pero se
    omite la repetición en la línea de la reserva — sería redundante, no
    hay ambigüedad posible con un solo edificio."""
    id_caba = obtener_repositorio(conn, "Localidad").crear(Localidad="CABA")
    id_ed = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1", Domicilio="Rivadavia 1", IdLocalidad=id_caba)
    id_un = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_ed, Departamento='7mo "L"')
    c1 = obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_un, NumeroConsultorio=1, ValorHoraAisladaActual=500)
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="A", Apellido="Aislada")
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=c1, Fecha="2026-08-05", HoraInicio=10, HoraFin=12,
        Estado="Confirmada", AplicaRecargo=0,
    )
    texto = mensaje_detalle_reserva_aislada(conn, id_profesional=id_prof, periodo="2026-08", incluir_edificio=True)
    assert texto.count("Edificio") == 1
    assert "Edificio Ramos 1: Rivadavia 1, CABA" in texto


def test_detalle_aislada_un_edificio_en_el_mensaje_aunque_el_sistema_tenga_mas(conn, profesional_aislada_con_edificios):
    """La decisión mira solo los edificios de ESTE mensaje, no los del
    sistema ni las llaves del profesional (ya no aplica la vieja "regla
    del edificio" general para este mensaje puntual): con una sola
    reserva, en un solo edificio, el mensaje lo menciona una vez arriba
    aunque el sistema tenga más de un edificio y el profesional tenga
    llaves de varios."""
    id_prof, c1, c2, id_ed1, id_ed2 = profesional_aislada_con_edificios
    id_llave = obtener_repositorio(conn, "Llave").crear(Nombre="Llave", Tipo="Unidad", ValorDepositoActual=5000)
    obtener_repositorio(conn, "LlaveAcceso").crear(IdLlave=id_llave, IdEdificio=id_ed1)
    obtener_repositorio(conn, "LlaveAcceso").crear(IdLlave=id_llave, IdEdificio=id_ed2)
    obtener_repositorio(conn, "LlaveMovimiento").crear(
        IdLlave=id_llave, Tipo="Asignación", IdProfesional=id_prof, Fecha="2026-07-02",
    )
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=c1, Fecha="2026-08-05", HoraInicio=10, HoraFin=12,
        Estado="Confirmada", AplicaRecargo=0,
    )
    texto = mensaje_detalle_reserva_aislada(conn, id_profesional=id_prof, periodo="2026-08")
    assert texto.count("Edificio") == 1
    assert "Edificio Ramos 1: Av. Rivadavia 1234, CABA" in texto


def test_detalle_aislada_sin_llaves_con_un_edificio_en_el_mensaje_lo_menciona(conn, profesional_aislada_con_edificios):
    """Un profesional sin ninguna llave todavía (recién empieza, alguien
    más le abre la puerta la primera vez) igual necesita saber la
    dirección del edificio de su reserva — ya no depende de si tiene
    llaves o no, solo de que el edificio aparezca en el mensaje."""
    id_prof, c1, _, _, _ = profesional_aislada_con_edificios
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=c1, Fecha="2026-08-05", HoraInicio=10, HoraFin=12,
        Estado="Confirmada", AplicaRecargo=0,
    )
    texto = mensaje_detalle_reserva_aislada(conn, id_profesional=id_prof, periodo="2026-08")
    assert "Edificio Ramos 1" in texto


def test_detalle_aislada_con_mas_de_un_edificio_en_el_mensaje_los_menciona_arriba_y_en_cada_linea(
    conn, profesional_aislada_con_edificios,
):
    """Con más de un edificio involucrado en el mensaje (del mes +
    posteriores) se agrega la dirección de cada uno arriba de todo Y se
    repite el edificio en la línea de cada reserva — para que el
    profesional no confunda a qué edificio corresponde cada unidad
    (pedido explícito de la clienta). Ya no depende de las llaves del
    profesional, a diferencia de la vieja "regla del edificio" general."""
    id_prof, c1, c2, id_ed1, id_ed2 = profesional_aislada_con_edificios
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=c1, Fecha="2026-08-05", HoraInicio=10, HoraFin=12,
        Estado="Confirmada", AplicaRecargo=0,
    )
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=c2, Fecha="2026-08-06", HoraInicio=10, HoraFin=12,
        Estado="Confirmada", AplicaRecargo=0,
    )
    texto = mensaje_detalle_reserva_aislada(conn, id_profesional=id_prof, periodo="2026-08")
    assert "Edificio Ramos 1: Av. Rivadavia 1234, CABA" in texto
    assert "Edificio San Justo 1: Belgrano 500, San Justo" in texto
    assert "- Edificio Ramos 1" in texto
    assert "- Edificio San Justo 1" in texto


def test_detalle_aislada_incluir_edificio_false_suprime_todo(conn, profesional_aislada_con_edificios):
    """`incluir_edificio=False` sigue funcionando como apagado total —
    ni la línea de arriba ni la mención en cada reserva, aunque el
    mensaje tenga más de un edificio."""
    id_prof, c1, c2, id_ed1, id_ed2 = profesional_aislada_con_edificios
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=c1, Fecha="2026-08-05", HoraInicio=10, HoraFin=12,
        Estado="Confirmada", AplicaRecargo=0,
    )
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=c2, Fecha="2026-08-06", HoraInicio=10, HoraFin=12,
        Estado="Confirmada", AplicaRecargo=0,
    )
    texto = mensaje_detalle_reserva_aislada(conn, id_profesional=id_prof, periodo="2026-08", incluir_edificio=False)
    assert "Edificio" not in texto


def test_detalle_aislada_un_edificio_en_dos_meses_distintos_no_repite_la_mencion(
    conn, profesional_aislada_con_edificios,
):
    """Escenario real reportado por la clienta: una reserva del mes en
    curso y otra para el mes siguiente, ambas en el mismo único edificio
    involucrado — la línea de arriba aparece una sola vez (no una por
    reserva) y ninguna de las dos líneas de detalle repite el edificio."""
    id_prof, c1, _, id_ed1, _ = profesional_aislada_con_edificios
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=c1, Fecha="2026-08-05", HoraInicio=10, HoraFin=12,
        Estado="Confirmada", AplicaRecargo=0,
    )
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=c1, Fecha="2026-09-03", HoraInicio=9, HoraFin=10,
        Estado="Confirmada", AplicaRecargo=0,
    )
    texto = mensaje_detalle_reserva_aislada(conn, id_profesional=id_prof, periodo="2026-08")
    assert texto.count("Edificio") == 1
    assert "Edificio Ramos 1: Av. Rivadavia 1234, CABA" in texto
    assert "RESERVAS POSTERIORES" in texto


def test_detalle_aislada_sin_placas_no_agrega_la_seccion(conn, profesional_aislada_con_edificios):
    """Pedido explícito de la clienta: si el profesional no tiene placa
    asignada en NINGUNA unidad involucrada en el mensaje, la sección
    "PLACAS PARA LOS TIMBRES" no aparece."""
    id_prof, c1, _, _, _ = profesional_aislada_con_edificios
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=c1, Fecha="2026-08-05", HoraInicio=10, HoraFin=12,
        Estado="Confirmada", AplicaRecargo=0,
    )
    texto = mensaje_detalle_reserva_aislada(conn, id_profesional=id_prof, periodo="2026-08")
    assert "PLACAS" not in texto


def test_detalle_aislada_con_placa_en_una_sola_unidad_solo_esa_linea(conn, profesional_aislada_con_edificios):
    """Con reservas en dos unidades distintas pero placa asignada en
    solo una de ellas, la sección solo menciona esa — la otra se omite
    sin avisar nada (el aviso de placa faltante ya existe aparte, al
    cargar la reserva)."""
    id_prof, c1, c2, id_ed1, id_ed2 = profesional_aislada_con_edificios
    id_un1 = obtener_repositorio(conn, "Consultorio").obtener(c1)["IdUnidad"]
    obtener_repositorio(conn, "Unidad").actualizar(id_un1, CantLimitePlacas=200)
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=c1, Fecha="2026-08-05", HoraInicio=10, HoraFin=12,
        Estado="Confirmada", AplicaRecargo=0,
    )
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=c2, Fecha="2026-08-06", HoraInicio=10, HoraFin=12,
        Estado="Confirmada", AplicaRecargo=0,
    )
    asignar_placa(conn, id_unidad=id_un1, posicion=75, id_profesional=id_prof)
    texto = mensaje_detalle_reserva_aislada(conn, id_profesional=id_prof, periodo="2026-08")
    seccion = texto.split("PLACAS PARA LOS TIMBRES")[1]
    assert 'Ramos 1 - 7mo "L": Posición 75' in seccion
    assert "San Justo" not in seccion


def test_detalle_aislada_con_placas_en_ambas_unidades_las_dos_lineas(conn, profesional_aislada_con_edificios):
    """Con placa asignada en las dos unidades involucradas, la sección
    lista las dos — mismo escenario que el ejemplo real dado por la
    clienta (Edificio Imperio, dos unidades, dos posiciones)."""
    id_prof, c1, c2, id_ed1, id_ed2 = profesional_aislada_con_edificios
    id_un1 = obtener_repositorio(conn, "Consultorio").obtener(c1)["IdUnidad"]
    id_un2 = obtener_repositorio(conn, "Consultorio").obtener(c2)["IdUnidad"]
    obtener_repositorio(conn, "Unidad").actualizar(id_un1, CantLimitePlacas=200)
    obtener_repositorio(conn, "Unidad").actualizar(id_un2, CantLimitePlacas=200)
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=c1, Fecha="2026-08-05", HoraInicio=10, HoraFin=12,
        Estado="Confirmada", AplicaRecargo=0,
    )
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=c2, Fecha="2026-09-03", HoraInicio=9, HoraFin=10,
        Estado="Confirmada", AplicaRecargo=0,
    )
    asignar_placa(conn, id_unidad=id_un1, posicion=75, id_profesional=id_prof)
    asignar_placa(conn, id_unidad=id_un2, posicion=145, id_profesional=id_prof)
    texto = mensaje_detalle_reserva_aislada(conn, id_profesional=id_prof, periodo="2026-08")
    assert "PLACAS PARA LOS TIMBRES" in texto
    assert texto.index("RESERVAS POSTERIORES") < texto.index("PLACAS PARA LOS TIMBRES")
    assert 'Ramos 1 - 7mo "L": Posición 75' in texto
    assert 'San Justo 1 - 3ro "B": Posición 145' in texto


def test_detalle_aislada_deposito_de_llave_del_mes(conn, profesional_aislada_con_edificios):
    id_prof, c1, _, id_ed1, _ = profesional_aislada_con_edificios
    id_llave = obtener_repositorio(conn, "Llave").crear(Nombre="Llave", Tipo="Unidad", ValorDepositoActual=5000)
    obtener_repositorio(conn, "LlaveAcceso").crear(IdLlave=id_llave, IdEdificio=id_ed1, IdUnidad=None)
    obtener_repositorio(conn, "LlaveMovimiento").crear(
        IdLlave=id_llave, Tipo="Asignación", IdProfesional=id_prof, Fecha="2026-08-02",
        DepositoCobrado=1, MontoCobrado=5000,
    )
    texto = mensaje_detalle_reserva_aislada(conn, id_profesional=id_prof, periodo="2026-08")
    assert "+ Depósito por llave unidad $5.000" in texto


def test_detalle_aislada_reintegro_de_llave_se_muestra_negativo(conn, profesional_aislada_con_edificios):
    id_prof, _, _, id_ed1, _ = profesional_aislada_con_edificios
    id_llave = obtener_repositorio(conn, "Llave").crear(Nombre="Llave", Tipo="Unidad", ValorDepositoActual=5000)
    obtener_repositorio(conn, "LlaveAcceso").crear(IdLlave=id_llave, IdEdificio=id_ed1, IdUnidad=None)
    id_asignacion = obtener_repositorio(conn, "LlaveMovimiento").crear(
        IdLlave=id_llave, Tipo="Asignación", IdProfesional=id_prof, Fecha="2026-07-01",
        DepositoCobrado=1, MontoCobrado=5000,
    )
    obtener_repositorio(conn, "LlaveMovimiento").crear(
        IdLlave=id_llave, Tipo="Devolución", IdProfesional=id_prof, Fecha="2026-08-02", IdAsignacion=id_asignacion,
        DepositoReintegrado=1, MontoReintegrado=5000,
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
    id_llave = obtener_repositorio(conn, "Llave").crear(Nombre="Llave", Tipo="Unidad", ValorDepositoActual=5000)
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


def test_detalle_aislada_sin_combinar_une_bloque_continuo_en_una_sola_linea(conn, profesional_aislada_con_edificios):
    """#44: por defecto (checks destildados), dos reservas del mismo
    consultorio sin ningún hueco entre medio (el HoraFin de una coincide
    con el HoraInicio de la siguiente) se muestran como UN solo bloque
    continuo — "10 a 14hs", no dos líneas ni un "y de"."""
    id_prof, c1, _, _, _ = profesional_aislada_con_edificios
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=c1, Fecha="2026-08-05", HoraInicio=10, HoraFin=12,
        Estado="Confirmada", AplicaRecargo=0,
    )
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=c1, Fecha="2026-08-05", HoraInicio=12, HoraFin=14,
        Estado="Confirmada", AplicaRecargo=0,
    )
    texto = mensaje_detalle_reserva_aislada(conn, id_profesional=id_prof, periodo="2026-08")
    assert "Miércoles 5/8 de 10 a 14hs" in texto
    assert "y de" not in texto
    assert "$2.000" in texto  # 4hs x 500 = 2000, una sola línea


def test_detalle_aislada_sin_combinar_bloque_continuo_no_mezcla_consultorios(
    conn, profesional_aislada_con_edificios,
):
    """Dos reservas a la misma hora exacta pero en consultorios distintos
    no son "el mismo bloque" — cada consultorio agrupa sus propios
    bloques continuos por separado."""
    id_prof, c1, c2, _, _ = profesional_aislada_con_edificios
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=c1, Fecha="2026-08-05", HoraInicio=10, HoraFin=12,
        Estado="Confirmada", AplicaRecargo=0,
    )
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=c2, Fecha="2026-08-05", HoraInicio=12, HoraFin=14,
        Estado="Confirmada", AplicaRecargo=0,
    )
    texto = mensaje_detalle_reserva_aislada(conn, id_profesional=id_prof, periodo="2026-08")
    assert "Miércoles 5/8 de 10 a 12hs" in texto
    assert "Miércoles 5/8 de 12 a 14hs" in texto
    assert "10 a 14" not in texto


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
