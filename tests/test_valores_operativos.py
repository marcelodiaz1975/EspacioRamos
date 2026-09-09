import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.valores_operativos import calcular_promedios_valor_hora_regular
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


def _unidad(conn, nombre_edificio="Ramos 1", departamento='7mo "L"', localidad=None):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre=nombre_edificio, DomicilioLocalidad=localidad)
    return obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento=departamento), id_edificio


def _consultorio(conn, id_unidad, numero=1, valor_regular=1000):
    return obtener_repositorio(conn, "Consultorio").crear(
        IdUnidad=id_unidad, NumeroConsultorio=numero, ValorHoraRegularActual=valor_regular,
    )


def test_sin_consultorios_devuelve_vacio(conn):
    promedios = calcular_promedios_valor_hora_regular(conn, [])
    assert promedios.general == 0.0
    assert promedios.por_localidad == []
    assert promedios.por_edificio == []
    assert promedios.por_unidad == []


def test_promedio_general_simple(conn):
    id_unidad, _ = _unidad(conn)
    id_c1 = _consultorio(conn, id_unidad, numero=1, valor_regular=1000)
    id_c2 = _consultorio(conn, id_unidad, numero=2, valor_regular=2000)
    conn.commit()

    promedios = calcular_promedios_valor_hora_regular(conn, [id_c1, id_c2])
    assert promedios.general == pytest.approx(1500)
    assert len(promedios.por_unidad) == 1
    assert promedios.por_unidad[0].promedio_valor_hora_regular == pytest.approx(1500)


def test_promedio_por_edificio_y_localidad(conn):
    id_unidad_1, id_edificio_1 = _unidad(conn, nombre_edificio="Ramos 1", departamento="1A", localidad="Ramos Mejía")
    id_unidad_2, id_edificio_2 = _unidad(conn, nombre_edificio="Ramos 2", departamento="1A", localidad="Ramos Mejía")
    id_unidad_3, id_edificio_3 = _unidad(conn, nombre_edificio="Haedo 1", departamento="1A", localidad="Haedo")
    id_c1 = _consultorio(conn, id_unidad_1, valor_regular=1000)
    id_c2 = _consultorio(conn, id_unidad_2, valor_regular=2000)
    id_c3 = _consultorio(conn, id_unidad_3, valor_regular=4000)
    conn.commit()

    promedios = calcular_promedios_valor_hora_regular(conn, [id_c1, id_c2, id_c3])
    assert len(promedios.por_edificio) == 3
    assert len(promedios.por_localidad) == 2
    por_localidad = {g.nombre: g.promedio_valor_hora_regular for g in promedios.por_localidad}
    assert por_localidad["Ramos Mejía"] == pytest.approx(1500)
    assert por_localidad["Haedo"] == pytest.approx(4000)


def test_localidad_sin_dato_se_agrupa_como_sin_localidad(conn):
    id_unidad, _ = _unidad(conn, localidad=None)
    id_c = _consultorio(conn, id_unidad, valor_regular=1000)
    conn.commit()

    promedios = calcular_promedios_valor_hora_regular(conn, [id_c])
    assert promedios.por_localidad[0].nombre == "(Sin localidad)"


def test_filtro_por_consultorio_puntual_no_incluye_los_demas_de_la_unidad(conn):
    id_unidad, _ = _unidad(conn)
    id_c1 = _consultorio(conn, id_unidad, numero=1, valor_regular=1000)
    _consultorio(conn, id_unidad, numero=2, valor_regular=5000)
    conn.commit()

    promedios = calcular_promedios_valor_hora_regular(conn, [id_c1])
    assert promedios.general == pytest.approx(1000)


def test_orden_por_unidad_sigue_criterio_de_piso(conn):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_u_7mo = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='7mo "L"')
    id_u_pb = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='PB "D"')
    id_u_ep = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='EP "K"')
    id_c1 = _consultorio(conn, id_u_7mo)
    id_c2 = _consultorio(conn, id_u_pb)
    id_c3 = _consultorio(conn, id_u_ep)
    conn.commit()

    promedios = calcular_promedios_valor_hora_regular(conn, [id_c1, id_c2, id_c3])
    assert [g.unidad for g in promedios.por_unidad] == ['PB "D"', 'EP "K"', '7mo "L"']
