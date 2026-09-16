import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.placas import (
    asignar_placa,
    liberar_posicion,
    listar_placas,
    nombre_estandar,
    nombre_grabado,
    posiciones_libres,
    texto_para_imprimir,
)
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


def _id_localidad(conn, nombre: str | None) -> int | None:
    if nombre is None:
        return None
    fila = conn.execute("SELECT IdLocalidad FROM Localidad WHERE Localidad = ?", (nombre,)).fetchone()
    return fila["IdLocalidad"] if fila else obtener_repositorio(conn, "Localidad").crear(Localidad=nombre)


def _crear_unidad(conn, nombre_edificio="Ramos 1", departamento="1ro A", localidad=None, limite_placas=10):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(
        Nombre=nombre_edificio, IdLocalidad=_id_localidad(conn, localidad)
    )
    id_unidad = obtener_repositorio(conn, "Unidad").crear(
        IdEdificio=id_edificio, Departamento=departamento, CantLimitePlacas=limite_placas,
    )
    return id_edificio, id_unidad


def _crear_profesional(conn, apellido="Lo Veci", nombre_pila="Virginia", tratamiento="Lic."):
    return obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="R", Apellido=apellido, NombrePila=nombre_pila, Tratamiento=tratamiento,
    )


def test_nombre_estandar_junta_tratamiento_nombre_apellido(conn):
    id_profesional = _crear_profesional(conn)
    profesional = obtener_repositorio(conn, "Profesional").obtener(id_profesional)
    assert nombre_estandar(profesional) == "Lic. Virginia Lo Veci"


def test_nombre_grabado_usa_el_personalizado_si_corresponde(conn):
    _, id_unidad = _crear_unidad(conn)
    id_profesional = _crear_profesional(conn)
    id_placa = asignar_placa(
        conn, id_unidad=id_unidad, posicion=1, id_profesional=id_profesional,
        es_personalizada=True, nombre_grabado_personalizado="Virginia",
    )
    placa = obtener_repositorio(conn, "Placa").obtener(id_placa)
    profesional = obtener_repositorio(conn, "Profesional").obtener(id_profesional)
    assert nombre_grabado(placa, profesional) == "Virginia"


def test_nombre_grabado_no_personalizada_usa_el_estandar(conn):
    _, id_unidad = _crear_unidad(conn)
    id_profesional = _crear_profesional(conn)
    id_placa = asignar_placa(conn, id_unidad=id_unidad, posicion=1, id_profesional=id_profesional)
    placa = obtener_repositorio(conn, "Placa").obtener(id_placa)
    profesional = obtener_repositorio(conn, "Profesional").obtener(id_profesional)
    assert nombre_grabado(placa, profesional) == "Lic. Virginia Lo Veci"


def test_texto_para_imprimir_sin_lineas_usa_el_estandar(conn):
    id_profesional = _crear_profesional(conn)
    profesional = obtener_repositorio(conn, "Profesional").obtener(id_profesional)
    assert texto_para_imprimir(profesional) == "Lic. Virginia Lo Veci"


def test_texto_para_imprimir_con_una_linea(conn):
    id_profesional = _crear_profesional(conn)
    profesional = obtener_repositorio(conn, "Profesional").obtener(id_profesional)
    assert texto_para_imprimir(profesional, linea1="Virginia") == "Virginia"


def test_texto_para_imprimir_con_dos_lineas(conn):
    id_profesional = _crear_profesional(conn)
    profesional = obtener_repositorio(conn, "Profesional").obtener(id_profesional)
    texto = texto_para_imprimir(profesional, linea1="Lic. Silvina Pugliese", linea2='Equipo "Sol terapias"')
    assert texto == 'Lic. Silvina Pugliese\nEquipo "Sol terapias"'


def test_asignar_placa_rechaza_posicion_fuera_de_rango(conn):
    _, id_unidad = _crear_unidad(conn, limite_placas=5)
    id_profesional = _crear_profesional(conn)
    with pytest.raises(ValueError):
        asignar_placa(conn, id_unidad=id_unidad, posicion=6, id_profesional=id_profesional)
    with pytest.raises(ValueError):
        asignar_placa(conn, id_unidad=id_unidad, posicion=0, id_profesional=id_profesional)


def test_asignar_placa_rechaza_profesional_inexistente(conn):
    _, id_unidad = _crear_unidad(conn)
    with pytest.raises(ValueError):
        asignar_placa(conn, id_unidad=id_unidad, posicion=1, id_profesional=99999)


def test_asignar_placa_en_posicion_ocupada_pisa_el_mismo_registro(conn):
    """Coincide con lo físico: la clienta rompe la placa vieja y arma la
    nueva antes de tocar el sistema — no se guarda ningún historial."""
    _, id_unidad = _crear_unidad(conn)
    id_profesional_viejo = _crear_profesional(conn, apellido="Viejo")
    id_profesional_nuevo = _crear_profesional(conn, apellido="Nuevo")

    id_placa = asignar_placa(conn, id_unidad=id_unidad, posicion=1, id_profesional=id_profesional_viejo)
    id_placa_reasignada = asignar_placa(conn, id_unidad=id_unidad, posicion=1, id_profesional=id_profesional_nuevo)

    assert id_placa == id_placa_reasignada
    placas = obtener_repositorio(conn, "Placa").listar(IdUnidad=id_unidad)
    assert len(placas) == 1
    assert placas[0]["IdProfesional"] == id_profesional_nuevo


def test_reasignar_sin_personalizar_borra_el_nombre_personalizado_anterior(conn):
    _, id_unidad = _crear_unidad(conn)
    id_profesional_viejo = _crear_profesional(conn, apellido="Viejo")
    id_profesional_nuevo = _crear_profesional(conn, apellido="Nuevo")
    asignar_placa(
        conn, id_unidad=id_unidad, posicion=1, id_profesional=id_profesional_viejo,
        es_personalizada=True, nombre_grabado_personalizado="Apodo",
    )

    asignar_placa(conn, id_unidad=id_unidad, posicion=1, id_profesional=id_profesional_nuevo)

    placa = obtener_repositorio(conn, "Placa").listar(IdUnidad=id_unidad)[0]
    assert placa["EsPersonalizada"] == 0
    assert placa["NombreGrabado"] is None


def test_posiciones_libres_excluye_las_ocupadas(conn):
    _, id_unidad = _crear_unidad(conn, limite_placas=3)
    id_profesional = _crear_profesional(conn)
    asignar_placa(conn, id_unidad=id_unidad, posicion=2, id_profesional=id_profesional)
    assert posiciones_libres(conn, id_unidad) == [1, 3]


def test_posiciones_libres_sin_capacidad_configurada_no_ofrece_nada(conn):
    _, id_unidad = _crear_unidad(conn, limite_placas=0)
    assert posiciones_libres(conn, id_unidad) == []


def test_liberar_posicion_borra_el_registro(conn):
    _, id_unidad = _crear_unidad(conn)
    id_profesional = _crear_profesional(conn)
    id_placa = asignar_placa(conn, id_unidad=id_unidad, posicion=1, id_profesional=id_profesional)

    liberar_posicion(conn, id_placa)

    assert obtener_repositorio(conn, "Placa").obtener(id_placa) is None
    assert posiciones_libres(conn, id_unidad) == list(range(1, 11))


def test_placa_sigue_figurando_aunque_el_profesional_ya_no_trabaje_ahi(conn):
    """A pedido de la clienta: no hay ningún estado de "vigente"/"no
    vigente" — el registro se deja tal cual hasta que se reasigna a
    mano, sin que el sistema avise nada."""
    _, id_unidad = _crear_unidad(conn)
    id_profesional = _crear_profesional(conn)
    asignar_placa(conn, id_unidad=id_unidad, posicion=1, id_profesional=id_profesional)

    placas = listar_placas(conn, id_profesional=id_profesional)

    assert len(placas) == 1
    assert placas[0]["IdUnidad"] == id_unidad


def test_listar_placas_filtra_por_profesional(conn):
    _, id_unidad = _crear_unidad(conn)
    id_1 = _crear_profesional(conn, apellido="Uno")
    id_2 = _crear_profesional(conn, apellido="Dos")
    asignar_placa(conn, id_unidad=id_unidad, posicion=1, id_profesional=id_1)
    asignar_placa(conn, id_unidad=id_unidad, posicion=2, id_profesional=id_2)

    placas = listar_placas(conn, id_profesional=id_1)

    assert len(placas) == 1
    assert placas[0]["IdProfesional"] == id_1


def test_listar_placas_filtra_por_localidad_edificio_y_unidad(conn):
    _, id_unidad_a = _crear_unidad(conn, nombre_edificio="Torre A", departamento="1A", localidad="Ramos Mejía")
    id_edificio_b, id_unidad_b = _crear_unidad(conn, nombre_edificio="Torre B", departamento="1B", localidad="Haedo")
    id_profesional = _crear_profesional(conn)
    asignar_placa(conn, id_unidad=id_unidad_a, posicion=1, id_profesional=id_profesional)
    asignar_placa(conn, id_unidad=id_unidad_b, posicion=1, id_profesional=id_profesional)

    assert len(listar_placas(conn, ids_localidad=[_id_localidad(conn, "Ramos Mejía")])) == 1
    assert len(listar_placas(conn, ids_edificio=[id_edificio_b])) == 1
    assert len(listar_placas(conn, ids_unidad=[id_unidad_a])) == 1
    assert len(listar_placas(conn)) == 2


def test_listar_placas_ordena_por_edificio_unidad_y_posicion(conn):
    _, id_unidad = _crear_unidad(conn)
    id_profesional = _crear_profesional(conn)
    asignar_placa(conn, id_unidad=id_unidad, posicion=2, id_profesional=id_profesional)
    asignar_placa(conn, id_unidad=id_unidad, posicion=1, id_profesional=id_profesional)

    placas = listar_placas(conn)

    assert [p["PosicionTablero"] for p in placas] == [1, 2]
