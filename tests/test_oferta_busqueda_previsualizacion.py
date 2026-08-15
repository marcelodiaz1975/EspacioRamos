import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.oferta_busqueda import Busqueda, CriteriosGlobales
from app.negocio.oferta_busqueda_texto import previsualizar_documento
from app.repositorio.registro import obtener_repositorio

ANIO, MES = 2026, 8


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


@pytest.fixture
def edificio_con_consultorio(conn):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='7mo "L"')
    obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=1, ValorHoraRegularActual=1000)
    return id_edificio


def _busqueda_simple(dias=("Lunes",)):
    return Busqueda(fecha_desde=f"{ANIO}-{MES:02d}-01", fecha_hasta=None, dias=list(dias), hora_desde=9, hora_hasta=11)


def test_una_fila_por_opcion_encontrada(conn, edificio_con_consultorio):
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[edificio_con_consultorio])

    filas = previsualizar_documento(conn, id_prof, globales, [_busqueda_simple()])

    assert len(filas) == 1
    i_busqueda, i_alt, i_op, texto = filas[0]
    assert (i_busqueda, i_alt, i_op) == (0, 0, 0)
    assert 'Lunes de 9 a 11hs consultorio 1 del 7mo "L"' in texto
    assert "Hora regular $ 1.000" in texto  # mostrar_valor=True: en la previsualización sí se ve el valor


def test_indices_por_busqueda_multiple(conn, edificio_con_consultorio):
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[edificio_con_consultorio])

    filas = previsualizar_documento(conn, id_prof, globales, [_busqueda_simple(["Lunes"]), _busqueda_simple(["Martes"])])

    indices_busqueda = {f[0] for f in filas}
    assert indices_busqueda == {0, 1}


def test_sin_alternativas_devuelve_lista_vacia(conn):
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[])
    assert previsualizar_documento(conn, id_prof, globales, [_busqueda_simple()]) == []


def test_paquete_y_incompleto_no_aparece_en_la_previsualizacion(conn, edificio_con_consultorio):
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[edificio_con_consultorio])
    franja_1 = Busqueda(
        fecha_desde=f"{ANIO}-{MES:02d}-01", fecha_hasta=None, dias=["Lunes"], hora_desde=9, hora_hasta=11,
        combinacion_con_siguiente="Y",
    )
    franja_2_sin_cobertura = Busqueda(fecha_desde=f"{ANIO}-{MES:02d}-01", fecha_hasta=None, dias=[], hora_desde=9, hora_hasta=11)

    filas = previsualizar_documento(conn, id_prof, globales, [franja_1, franja_2_sin_cobertura])

    assert filas == []


def test_categoria_c_anonimiza_en_la_previsualizacion(conn, edificio_con_consultorio):
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="C", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[edificio_con_consultorio])

    filas = previsualizar_documento(conn, id_prof, globales, [_busqueda_simple()])

    assert '7mo "L"' not in filas[0][3]


def test_sin_profesional_lanza_error(conn):
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[])
    with pytest.raises(ValueError):
        previsualizar_documento(conn, 999, globales, [_busqueda_simple()])
