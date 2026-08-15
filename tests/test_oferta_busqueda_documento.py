import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.oferta_busqueda import Busqueda, CriteriosGlobales, resolver_busquedas_documento
from app.repositorio.registro import obtener_repositorio

ANIO, MES = 2026, 8


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


def _crear_edificio_con_consultorio(conn, nombre, departamento):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre=nombre)
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento=departamento)
    obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=1, ValorHoraRegularActual=1000)
    return id_edificio


def _busqueda(dia, combinacion_con_siguiente=None):
    return Busqueda(
        fecha_desde=f"{ANIO}-{MES:02d}-01", fecha_hasta=None, dias=[dia], hora_desde=9, hora_hasta=11,
        combinacion_con_siguiente=combinacion_con_siguiente,
    )


def test_sin_combinacion_cada_busqueda_es_independiente(conn):
    id_edificio = _crear_edificio_con_consultorio(conn, "Ramos 1", '7mo "L"')
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    # "Sábado" no tiene reservas, pero tampoco cobertura buscada aparte del consultorio existente: ambas cubren.
    busquedas = [_busqueda("Lunes"), _busqueda("Martes")]

    resultado = resolver_busquedas_documento(conn, globales, busquedas)

    assert len(resultado[0]) == 1
    assert len(resultado[1]) == 1


def test_grupo_y_con_todas_cubiertas_se_mantiene_entero(conn):
    id_edificio = _crear_edificio_con_consultorio(conn, "Ramos 1", '7mo "L"')
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    busquedas = [_busqueda("Lunes", combinacion_con_siguiente="Y"), _busqueda("Martes")]

    resultado = resolver_busquedas_documento(conn, globales, busquedas)

    assert len(resultado[0]) == 1
    assert len(resultado[1]) == 1


def test_grupo_y_con_una_sin_cobertura_descarta_todo_el_paquete(conn):
    id_edificio = _crear_edificio_con_consultorio(conn, "Ramos 1", '7mo "L"')
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    # La segunda búsqueda pide un edificio inexistente: nunca tiene cobertura.
    busquedas = [
        _busqueda("Lunes", combinacion_con_siguiente="Y"),
        Busqueda(fecha_desde=f"{ANIO}-{MES:02d}-01", fecha_hasta=None, dias=[], hora_desde=9, hora_hasta=11),
    ]

    resultado = resolver_busquedas_documento(conn, globales, busquedas)

    assert resultado[0] == []
    assert resultado[1] == []


def test_grupo_o_independiente_no_se_ve_afectado_por_paquete_incompleto(conn):
    id_edificio = _crear_edificio_con_consultorio(conn, "Ramos 1", '7mo "L"')
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    busquedas = [
        _busqueda("Lunes", combinacion_con_siguiente="Y"),
        Busqueda(fecha_desde=f"{ANIO}-{MES:02d}-01", fecha_hasta=None, dias=[], hora_desde=9, hora_hasta=11),  # sin cobertura, en el paquete Y
        _busqueda("Miércoles"),  # suelta ("O"), independiente del paquete anterior
    ]

    resultado = resolver_busquedas_documento(conn, globales, busquedas)

    assert resultado[0] == []  # paquete Y incompleto: se descarta entera
    assert resultado[1] == []
    assert len(resultado[2]) == 1  # independiente: se mantiene


def test_lista_vacia_devuelve_lista_vacia(conn):
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[])
    assert resolver_busquedas_documento(conn, globales, []) == []
