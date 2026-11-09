import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.oferta_busqueda import Busqueda, CriteriosGlobales
from app.negocio.oferta_busqueda_texto import opciones_a_destildar_por_bloque, previsualizar_documento
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
    i_busqueda, i_alt, i_op, texto, hora_inicio, hora_fin = filas[0]
    assert (i_busqueda, i_alt, i_op) == (0, 0, 0)
    assert 'Lunes de 9 a 11hs consultorio 1 del 7mo "L"' in texto
    assert "Hora regular $ 1.000" in texto  # mostrar_valor=True: en la previsualización sí se ve el valor
    assert (hora_inicio, hora_fin) == (9, 11)


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


def test_categoria_c_no_se_anonimiza_en_la_previsualizacion(conn, edificio_con_consultorio):
    """Pedido explícito de la clienta: la previsualización (pantalla de
    la operadora) tiene que identificar siempre la ubicación real para
    que pueda tildar/destildar con criterio — la anonimización de
    categoría C (`detalle_tramo`, `anonimizar=True`) es una regla del
    DOCUMENTO final que recibe el profesional, no de esta pantalla."""
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="C", Apellido="Prueba")
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[edificio_con_consultorio])

    filas = previsualizar_documento(conn, id_prof, globales, [_busqueda_simple()])

    assert '7mo "L"' in filas[0][3]


def test_identificar_unidad_desactivado_no_afecta_la_previsualizacion(conn, edificio_con_consultorio):
    """Mismo motivo que el test de categoría C: "Identificar unidad"/
    "Identificar consultorio" solo rigen lo que ve el profesional en el
    documento final, nunca la previsualización."""
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    globales = CriteriosGlobales(
        tipo_busqueda="Regular", ids_edificio=[edificio_con_consultorio],
        identificar_unidad=False, identificar_consultorio=False,
    )

    filas = previsualizar_documento(conn, id_prof, globales, [_busqueda_simple()])

    assert "consultorio 1" in filas[0][3]
    assert '7mo "L"' in filas[0][3]


def test_localidad_se_antepone_solo_si_hay_mas_de_una(conn):
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Prueba")
    id_localidad_1 = obtener_repositorio(conn, "Localidad").crear(Localidad="Ramos Mejía")
    id_localidad_2 = obtener_repositorio(conn, "Localidad").crear(Localidad="Haedo")
    id_edificio_1 = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1", IdLocalidad=id_localidad_1)
    id_unidad_1 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio_1, Departamento='7mo "L"')
    obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad_1, NumeroConsultorio=1, ValorHoraRegularActual=1000)
    id_edificio_2 = obtener_repositorio(conn, "Edificio").crear(Nombre="Haedo 1", IdLocalidad=id_localidad_2)
    id_unidad_2 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio_2, Departamento='PB "A"')
    obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad_2, NumeroConsultorio=2, ValorHoraRegularActual=1000)

    globales_una_localidad = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio_1])
    filas = previsualizar_documento(conn, id_prof, globales_una_localidad, [_busqueda_simple()])
    assert "Ramos Mejía" not in filas[0][3]

    globales_dos_localidades = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio_1, id_edificio_2])
    filas = previsualizar_documento(conn, id_prof, globales_dos_localidades, [_busqueda_simple()])
    textos = [f[3] for f in filas]
    assert any(t.startswith("Ramos Mejía - ") for t in textos)
    assert any(t.startswith("Haedo - ") for t in textos)


def test_opciones_a_destildar_por_bloque_mantiene_la_mas_extensa_del_grupo_superpuesto():
    """Ejemplo real de la clienta: lunes 9-18hs con 3hs mínimas da las
    alternativas 9-13hs, 9-12hs y 14-18hs — 14-18hs no se superpone con
    nada (no se toca) y, de las otras dos (que sí se superponen entre
    sí), se destilda la más corta (9-12hs)."""
    filas = [
        (0, 0, 0, "9 a 13hs", 9, 13),
        (0, 0, 1, "9 a 12hs", 9, 12),
        (0, 0, 2, "14 a 18hs", 14, 18),
    ]
    assert opciones_a_destildar_por_bloque(filas) == {(0, 0, 1)}


def test_opciones_a_destildar_por_bloque_no_toca_nada_sin_superposicion():
    filas = [(0, 0, 0, "9 a 11hs", 9, 11), (0, 0, 1, "11 a 13hs", 11, 13)]
    assert opciones_a_destildar_por_bloque(filas) == set()


def test_opciones_a_destildar_por_bloque_empate_no_destilda_a_ninguna():
    """Pedido explícito de la clienta: con un empate exacto de extensión
    entre las que se superponen, las deja todas tildadas — queda a su
    criterio en el momento."""
    filas = [(0, 0, 0, "9 a 13hs", 9, 13), (0, 0, 1, "10 a 14hs", 10, 14)]
    assert opciones_a_destildar_por_bloque(filas) == set()


def test_opciones_a_destildar_por_bloque_superposicion_transitiva():
    """A se superpone con B, B con C, pero A y C no se tocan entre sí —
    los tres forman un único grupo y gana la de mayor extensión."""
    filas = [
        (0, 0, 0, "9 a 12hs", 9, 12),
        (0, 0, 1, "11 a 16hs", 11, 16),
        (0, 0, 2, "15 a 17hs", 15, 17),
    ]
    assert opciones_a_destildar_por_bloque(filas) == {(0, 0, 0), (0, 0, 2)}


def test_opciones_a_destildar_por_bloque_agrupa_por_dia_por_separado():
    filas = [
        (0, 0, 0, "lunes 9 a 13hs", 9, 13),
        (0, 0, 1, "lunes 9 a 12hs", 9, 12),
        (0, 1, 0, "martes 9 a 13hs", 9, 13),
        (0, 1, 1, "martes 9 a 12hs", 9, 12),
    ]
    assert opciones_a_destildar_por_bloque(filas) == {(0, 0, 1), (0, 1, 1)}


def test_sin_profesional_lanza_error(conn):
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[])
    with pytest.raises(ValueError):
        previsualizar_documento(conn, 999, globales, [_busqueda_simple()])
