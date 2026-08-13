import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.lista_espera import (
    AMARILLO,
    NARANJA,
    ROJO,
    VERDE,
    calcular_coincidencia,
    crear_pedido,
    marcar_descartado,
    marcar_resuelto,
)
from app.repositorio.registro import obtener_repositorio

ANIO, MES = 2026, 8


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


def _crear_edificio(conn, nombre="Ramos 1"):
    return obtener_repositorio(conn, "Edificio").crear(Nombre=nombre)


def _crear_unidad(conn, id_edificio, departamento):
    return obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento=departamento)


def _crear_consultorio(conn, id_unidad, numero, **kwargs):
    return obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=numero, **kwargs)


def _ocupar(conn, id_consultorio, dia, hora_inicio, hora_fin):
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Ocupante")
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof, IdConsultorio=id_consultorio, DiaSemana=dia,
        HoraInicio=hora_inicio, HoraFin=hora_fin, VigenciaInicio="2026-01-01",
    )


def _profesional(conn):
    return obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="C", Apellido="Interesado")


def test_verde_un_solo_consultorio_cubre_todo(conn):
    id_edificio = _crear_edificio(conn)
    id_unidad = _crear_unidad(conn, id_edificio, '7mo "L"')
    id_consultorio = _crear_consultorio(conn, id_unidad, 1)

    id_pedido = crear_pedido(
        conn, id_profesional=_profesional(conn), tipo_combinacion="O",
        dias=["Lunes"], horario_desde=14, horario_hasta=16,
    )
    pedido = obtener_repositorio(conn, "ListaEspera").obtener(id_pedido)
    coincidencia = calcular_coincidencia(conn, pedido, ANIO, MES)

    assert coincidencia.color == VERDE
    assert coincidencia.dias_cubiertos == ["Lunes"]
    assert len(coincidencia.tramos_por_dia["Lunes"]) == 1
    assert coincidencia.tramos_por_dia["Lunes"][0].id_consultorio == id_consultorio


def test_amarillo_combina_consultorios_misma_unidad(conn):
    id_edificio = _crear_edificio(conn)
    id_unidad = _crear_unidad(conn, id_edificio, '7mo "L"')
    id_a = _crear_consultorio(conn, id_unidad, 1)
    id_b = _crear_consultorio(conn, id_unidad, 2)
    _ocupar(conn, id_a, "Lunes", 15, 16)  # A libre 14-15
    _ocupar(conn, id_b, "Lunes", 14, 15)  # B libre 15-16

    id_pedido = crear_pedido(
        conn, id_profesional=_profesional(conn), tipo_combinacion="O",
        dias=["Lunes"], horario_desde=14, horario_hasta=16,
    )
    pedido = obtener_repositorio(conn, "ListaEspera").obtener(id_pedido)
    coincidencia = calcular_coincidencia(conn, pedido, ANIO, MES)

    assert coincidencia.color == AMARILLO
    ids_usados = {t.id_consultorio for t in coincidencia.tramos_por_dia["Lunes"]}
    assert ids_usados == {id_a, id_b}


def test_naranja_combina_consultorios_mismo_edificio_distinta_unidad(conn):
    id_edificio = _crear_edificio(conn)
    id_unidad_a = _crear_unidad(conn, id_edificio, '7mo "L"')
    id_unidad_b = _crear_unidad(conn, id_edificio, 'EP "K"')
    id_a = _crear_consultorio(conn, id_unidad_a, 1)
    id_b = _crear_consultorio(conn, id_unidad_b, 1)
    _ocupar(conn, id_a, "Lunes", 15, 16)
    _ocupar(conn, id_b, "Lunes", 14, 15)

    id_pedido = crear_pedido(
        conn, id_profesional=_profesional(conn), tipo_combinacion="O",
        dias=["Lunes"], horario_desde=14, horario_hasta=16,
    )
    pedido = obtener_repositorio(conn, "ListaEspera").obtener(id_pedido)
    coincidencia = calcular_coincidencia(conn, pedido, ANIO, MES)

    assert coincidencia.color == NARANJA


def test_rojo_combina_consultorios_distinto_edificio(conn):
    id_edificio_a = _crear_edificio(conn, "Ramos 1")
    id_edificio_b = _crear_edificio(conn, "Ramos 2")
    id_unidad_a = _crear_unidad(conn, id_edificio_a, '7mo "L"')
    id_unidad_b = _crear_unidad(conn, id_edificio_b, 'PB "A"')
    id_a = _crear_consultorio(conn, id_unidad_a, 1)
    id_b = _crear_consultorio(conn, id_unidad_b, 1)
    _ocupar(conn, id_a, "Lunes", 15, 16)
    _ocupar(conn, id_b, "Lunes", 14, 15)

    id_pedido = crear_pedido(
        conn, id_profesional=_profesional(conn), tipo_combinacion="O",
        dias=["Lunes"], horario_desde=14, horario_hasta=16,
    )
    pedido = obtener_repositorio(conn, "ListaEspera").obtener(id_pedido)
    coincidencia = calcular_coincidencia(conn, pedido, ANIO, MES)

    assert coincidencia.color == ROJO


def test_sin_color_si_no_hay_forma_de_cubrir(conn):
    id_edificio = _crear_edificio(conn)
    id_unidad = _crear_unidad(conn, id_edificio, '7mo "L"')
    id_consultorio = _crear_consultorio(conn, id_unidad, 1)
    _ocupar(conn, id_consultorio, "Lunes", 14, 16)  # el único consultorio, ocupado todo el rango pedido

    id_pedido = crear_pedido(
        conn, id_profesional=_profesional(conn), tipo_combinacion="O",
        dias=["Lunes"], horario_desde=14, horario_hasta=16,
    )
    pedido = obtener_repositorio(conn, "ListaEspera").obtener(id_pedido)
    coincidencia = calcular_coincidencia(conn, pedido, ANIO, MES)
    assert coincidencia is None


def test_tipo_o_alcanza_con_un_dia_disponible(conn):
    id_edificio = _crear_edificio(conn)
    id_unidad = _crear_unidad(conn, id_edificio, '7mo "L"')
    id_consultorio = _crear_consultorio(conn, id_unidad, 1)
    _ocupar(conn, id_consultorio, "Martes", 14, 16)  # martes ocupado, lunes libre

    id_pedido = crear_pedido(
        conn, id_profesional=_profesional(conn), tipo_combinacion="O",
        dias=["Lunes", "Martes"], horario_desde=14, horario_hasta=16,
    )
    pedido = obtener_repositorio(conn, "ListaEspera").obtener(id_pedido)
    coincidencia = calcular_coincidencia(conn, pedido, ANIO, MES)

    assert coincidencia is not None
    assert coincidencia.dias_cubiertos == ["Lunes"]


def test_tipo_y_requiere_todos_los_dias(conn):
    id_edificio = _crear_edificio(conn)
    id_unidad = _crear_unidad(conn, id_edificio, '7mo "L"')
    id_consultorio = _crear_consultorio(conn, id_unidad, 1)
    _ocupar(conn, id_consultorio, "Martes", 14, 16)  # martes ocupado -> Y no puede cumplir ambos días

    id_pedido = crear_pedido(
        conn, id_profesional=_profesional(conn), tipo_combinacion="Y",
        dias=["Lunes", "Martes"], horario_desde=14, horario_hasta=16,
    )
    pedido = obtener_repositorio(conn, "ListaEspera").obtener(id_pedido)
    coincidencia = calcular_coincidencia(conn, pedido, ANIO, MES)
    assert coincidencia is None


def test_condicion_ventana_filtra_consultorios(conn):
    id_edificio = _crear_edificio(conn)
    id_unidad = _crear_unidad(conn, id_edificio, '7mo "L"')
    _crear_consultorio(conn, id_unidad, 1, Ventana=0)  # sin ventana, no cuenta

    id_pedido = crear_pedido(
        conn, id_profesional=_profesional(conn), tipo_combinacion="O",
        dias=["Lunes"], horario_desde=14, horario_hasta=16,
        condiciones_consultorio={"ventana": True},
    )
    pedido = obtener_repositorio(conn, "ListaEspera").obtener(id_pedido)
    coincidencia = calcular_coincidencia(conn, pedido, ANIO, MES)
    assert coincidencia is None


def test_marcar_resuelto_y_descartado(conn):
    id_edificio = _crear_edificio(conn)
    id_unidad = _crear_unidad(conn, id_edificio, '7mo "L"')
    _crear_consultorio(conn, id_unidad, 1)
    id_pedido_1 = crear_pedido(
        conn, id_profesional=_profesional(conn), tipo_combinacion="O",
        dias=["Lunes"], horario_desde=14, horario_hasta=16,
    )
    id_pedido_2 = crear_pedido(
        conn, id_profesional=_profesional(conn), tipo_combinacion="O",
        dias=["Martes"], horario_desde=14, horario_hasta=16,
    )

    marcar_resuelto(conn, id_pedido_1)
    marcar_descartado(conn, id_pedido_2, observacion="no le interesó el horario")

    repo = obtener_repositorio(conn, "ListaEspera")
    assert repo.obtener(id_pedido_1)["Estado"] == "Resuelto"
    assert repo.obtener(id_pedido_2)["Estado"] == "Descartado"
    assert repo.obtener(id_pedido_2)["ObservacionCierre"] == "no le interesó el horario"

    with pytest.raises(ValueError):
        marcar_resuelto(conn, id_pedido_1)  # ya no está Activo


def test_cantidad_horas_encuentra_subrango_libre_dentro_del_rango_pedido(conn):
    """De 9 a 13hs el consultorio está ocupado de 9 a 11 y libre de 11 a
    13 — pidiendo 2hs "en algún punto" del rango (sin importar cuáles)
    tiene que encontrar el sub-rango 11-13, no descartar el pedido solo
    porque el rango completo (9-13) no está libre."""
    id_edificio = _crear_edificio(conn)
    id_unidad = _crear_unidad(conn, id_edificio, '7mo "L"')
    id_consultorio = _crear_consultorio(conn, id_unidad, 1)
    _ocupar(conn, id_consultorio, "Lunes", 9, 11)

    id_pedido = crear_pedido(
        conn, id_profesional=_profesional(conn), tipo_combinacion="O", dias=["Lunes"],
        horario_desde=9, horario_hasta=13, cantidad_horas_requeridas=2,
    )
    pedido = obtener_repositorio(conn, "ListaEspera").obtener(id_pedido)
    coincidencia = calcular_coincidencia(conn, pedido, ANIO, MES)

    assert coincidencia.color == VERDE
    tramo = coincidencia.tramos_por_dia["Lunes"][0]
    assert (tramo.hora_inicio, tramo.hora_fin) == (11, 13)


def test_cantidad_horas_sin_ningun_subrango_libre_no_da_coincidencia(conn):
    id_edificio = _crear_edificio(conn)
    id_unidad = _crear_unidad(conn, id_edificio, '7mo "L"')
    id_consultorio = _crear_consultorio(conn, id_unidad, 1)
    _ocupar(conn, id_consultorio, "Lunes", 9, 12)  # solo queda 1hs libre (12-13), no alcanzan las 2hs pedidas

    id_pedido = crear_pedido(
        conn, id_profesional=_profesional(conn), tipo_combinacion="O", dias=["Lunes"],
        horario_desde=9, horario_hasta=13, cantidad_horas_requeridas=2,
    )
    pedido = obtener_repositorio(conn, "ListaEspera").obtener(id_pedido)
    coincidencia = calcular_coincidencia(conn, pedido, ANIO, MES)
    assert coincidencia is None


def test_cantidad_horas_mayor_al_rango_pedido_lanza_error(conn):
    with pytest.raises(ValueError):
        crear_pedido(
            conn, id_profesional=_profesional(conn), tipo_combinacion="O", dias=["Lunes"],
            horario_desde=9, horario_hasta=11, cantidad_horas_requeridas=3,
        )
