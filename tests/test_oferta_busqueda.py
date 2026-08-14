import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.oferta_busqueda import (
    AMARILLO,
    NARANJA,
    VERDE,
    Busqueda,
    CriteriosGlobales,
    resolver_busqueda,
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


def _ocupar_regular(conn, id_consultorio, dia, hora_inicio, hora_fin, vigencia_inicio="2020-01-01", vigencia_fin=None):
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Ocupante")
    obtener_repositorio(conn, "ReservaRegular").crear(
        IdProfesional=id_prof, IdConsultorio=id_consultorio, DiaSemana=dia,
        HoraInicio=hora_inicio, HoraFin=hora_fin, VigenciaInicio=vigencia_inicio, VigenciaFin=vigencia_fin,
    )


def _ocupar_aislada(conn, id_consultorio, fecha, hora_inicio, hora_fin):
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Ocupante")
    obtener_repositorio(conn, "ReservaAislada").crear(
        IdProfesional=id_prof, IdConsultorio=id_consultorio, Fecha=fecha, HoraInicio=hora_inicio, HoraFin=hora_fin,
    )


def test_regular_verde_un_consultorio_cubre_todo(conn):
    id_edificio = _crear_edificio(conn)
    id_unidad = _crear_unidad(conn, id_edificio, '7mo "L"')
    id_consultorio = _crear_consultorio(conn, id_unidad, 1)
    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    busqueda = Busqueda(fecha_desde=f"{ANIO}-{MES:02d}-01", fecha_hasta=None, dias=["Lunes"], hora_desde=9, hora_hasta=11)

    resultado = resolver_busqueda(conn, globales, busqueda)

    assert len(resultado.alternativas) == 1
    alt = resultado.alternativas[0]
    assert alt.color == VERDE
    assert alt.fecha is None
    assert alt.tramos[0].id_consultorio == id_consultorio


def test_regular_exige_todos_los_dias_pedidos(conn):
    """Si un día pedido no tiene cobertura, la búsqueda entera queda sin
    alternativas (regular: todos los días tienen que coincidir)."""
    id_edificio = _crear_edificio(conn)
    id_unidad = _crear_unidad(conn, id_edificio, '7mo "L"')
    id_consultorio = _crear_consultorio(conn, id_unidad, 1)
    _ocupar_regular(conn, id_consultorio, "Martes", 9, 11)

    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    busqueda = Busqueda(
        fecha_desde=f"{ANIO}-{MES:02d}-01", fecha_hasta=None, dias=["Lunes", "Martes"], hora_desde=9, hora_hasta=11,
    )
    resultado = resolver_busqueda(conn, globales, busqueda)
    assert resultado.alternativas == []


def test_aislada_alternativas_no_requieren_todas_las_fechas(conn):
    """Aislada: alcanza con que ALGUNAS fechas del rango tengan cobertura,
    no todas."""
    id_edificio = _crear_edificio(conn)
    id_unidad = _crear_unidad(conn, id_edificio, '7mo "L"')
    id_consultorio = _crear_consultorio(conn, id_unidad, 1)
    # 2026-08-03 es lunes, 2026-08-10 es el lunes siguiente.
    _ocupar_aislada(conn, id_consultorio, "2026-08-03", 9, 11)

    globales = CriteriosGlobales(tipo_busqueda="Aislada", ids_edificio=[id_edificio])
    busqueda = Busqueda(
        fecha_desde="2026-08-03", fecha_hasta="2026-08-10", dias=["Lunes"], hora_desde=9, hora_hasta=11,
    )
    resultado = resolver_busqueda(conn, globales, busqueda)

    assert len(resultado.alternativas) == 1
    assert resultado.alternativas[0].fecha == "2026-08-10"


def test_combinar_consultorios_false_rechaza_cobertura_combinada(conn):
    id_edificio = _crear_edificio(conn)
    id_unidad = _crear_unidad(conn, id_edificio, '7mo "L"')
    id_c1 = _crear_consultorio(conn, id_unidad, 1)
    id_c2 = _crear_consultorio(conn, id_unidad, 2)
    _ocupar_regular(conn, id_c1, "Lunes", 10, 11)
    _ocupar_regular(conn, id_c2, "Lunes", 9, 10)

    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    busqueda = Busqueda(
        fecha_desde=f"{ANIO}-{MES:02d}-01", fecha_hasta=None, dias=["Lunes"], hora_desde=9, hora_hasta=11,
        combinar_consultorios=False,
    )
    assert resolver_busqueda(conn, globales, busqueda).alternativas == []

    busqueda.combinar_consultorios = True
    resultado = resolver_busqueda(conn, globales, busqueda)
    assert len(resultado.alternativas) == 1
    assert resultado.alternativas[0].color == AMARILLO


def test_combinacion_nunca_cruza_edificios(conn):
    """Con 2 edificios en el alcance, cada uno es un canal independiente:
    si ninguno solo puede cubrir todo el rango, la búsqueda no combina
    consultorios entre ambos (no existe un color "naranja entre
    edificios" ni equivalente a rojo)."""
    id_edificio1 = _crear_edificio(conn, "Ramos 1")
    id_edificio2 = _crear_edificio(conn, "Ramos 2")
    id_unidad1 = _crear_unidad(conn, id_edificio1, '7mo "L"')
    id_unidad2 = _crear_unidad(conn, id_edificio2, '3ro "B"')
    id_c1 = _crear_consultorio(conn, id_unidad1, 1)
    id_c2 = _crear_consultorio(conn, id_unidad2, 1)
    _ocupar_regular(conn, id_c1, "Lunes", 10, 11)
    _ocupar_regular(conn, id_c2, "Lunes", 9, 10)

    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio1, id_edificio2])
    busqueda = Busqueda(
        fecha_desde=f"{ANIO}-{MES:02d}-01", fecha_hasta=None, dias=["Lunes"], hora_desde=9, hora_hasta=11,
    )
    assert resolver_busqueda(conn, globales, busqueda).alternativas == []


def test_cantidad_horas_minimas_encuentra_subrango(conn):
    id_edificio = _crear_edificio(conn)
    id_unidad = _crear_unidad(conn, id_edificio, '7mo "L"')
    id_consultorio = _crear_consultorio(conn, id_unidad, 1)
    _ocupar_regular(conn, id_consultorio, "Lunes", 9, 11)

    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    busqueda = Busqueda(
        fecha_desde=f"{ANIO}-{MES:02d}-01", fecha_hasta=None, dias=["Lunes"], hora_desde=9, hora_hasta=13,
        cantidad_horas_minimas=2,
    )
    resultado = resolver_busqueda(conn, globales, busqueda)
    assert len(resultado.alternativas) == 1
    tramo = resultado.alternativas[0].tramos[0]
    assert (tramo.hora_inicio, tramo.hora_fin) == (11, 13)


def test_valor_maximo_hora_descarta_consultorios_caros(conn):
    id_edificio = _crear_edificio(conn)
    id_unidad = _crear_unidad(conn, id_edificio, '7mo "L"')
    _crear_consultorio(conn, id_unidad, 1, ValorHoraRegularActual=5000)

    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    busqueda = Busqueda(
        fecha_desde=f"{ANIO}-{MES:02d}-01", fecha_hasta=None, dias=["Lunes"], hora_desde=9, hora_hasta=11,
        valor_maximo_hora=3000,
    )
    assert resolver_busqueda(conn, globales, busqueda).alternativas == []


def test_sillones_y_tamano_filtran_candidatos(conn):
    id_edificio = _crear_edificio(conn)
    id_unidad = _crear_unidad(conn, id_edificio, '7mo "L"')
    _crear_consultorio(conn, id_unidad, 1, Sillones=0, TamanoClasificacion="chico")
    id_c_grande = _crear_consultorio(conn, id_unidad, 2, Sillones=1, TamanoClasificacion="grande")

    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    busqueda = Busqueda(
        fecha_desde=f"{ANIO}-{MES:02d}-01", fecha_hasta=None, dias=["Lunes"], hora_desde=9, hora_hasta=11,
        sillones=True, tamano="grande",
    )
    resultado = resolver_busqueda(conn, globales, busqueda)
    assert resultado.alternativas[0].tramos[0].id_consultorio == id_c_grande


def test_naranja_combina_unidades_distintas_mismo_edificio(conn):
    id_edificio = _crear_edificio(conn)
    id_unidad1 = _crear_unidad(conn, id_edificio, '7mo "L"')
    id_unidad2 = _crear_unidad(conn, id_edificio, '3ro "B"')
    id_c1 = _crear_consultorio(conn, id_unidad1, 1)
    id_c2 = _crear_consultorio(conn, id_unidad2, 1)
    _ocupar_regular(conn, id_c1, "Lunes", 10, 11)
    _ocupar_regular(conn, id_c2, "Lunes", 9, 10)

    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    busqueda = Busqueda(
        fecha_desde=f"{ANIO}-{MES:02d}-01", fecha_hasta=None, dias=["Lunes"], hora_desde=9, hora_hasta=11,
    )
    resultado = resolver_busqueda(conn, globales, busqueda)
    assert resultado.alternativas[0].color == NARANJA


def test_regular_avisa_hora_aislada_superpuesta_sin_bloquear(conn):
    """Una ReservaAislada no bloquea la disponibilidad regular (se ignora
    para calcular ocupación), pero si cae dentro del bloque ofrecido tiene
    que avisarse — 2026-08-10 es lunes."""
    id_edificio = _crear_edificio(conn)
    id_unidad = _crear_unidad(conn, id_edificio, '7mo "L"')
    id_consultorio = _crear_consultorio(conn, id_unidad, 1)
    _ocupar_aislada(conn, id_consultorio, "2026-08-10", 9, 10)

    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    busqueda = Busqueda(fecha_desde=f"{ANIO}-{MES:02d}-01", fecha_hasta=None, dias=["Lunes"], hora_desde=9, hora_hasta=11)
    resultado = resolver_busqueda(conn, globales, busqueda)

    assert len(resultado.alternativas) == 1  # no se bloquea
    alt = resultado.alternativas[0]
    assert alt.color == VERDE
    assert len(alt.avisos) == 1
    assert "2026-08-10" in alt.avisos[0]


def test_regular_sin_hora_aislada_no_genera_avisos(conn):
    id_edificio = _crear_edificio(conn)
    id_unidad = _crear_unidad(conn, id_edificio, '7mo "L"')
    _crear_consultorio(conn, id_unidad, 1)

    globales = CriteriosGlobales(tipo_busqueda="Regular", ids_edificio=[id_edificio])
    busqueda = Busqueda(fecha_desde=f"{ANIO}-{MES:02d}-01", fecha_hasta=None, dias=["Lunes"], hora_desde=9, hora_hasta=11)
    resultado = resolver_busqueda(conn, globales, busqueda)
    assert resultado.alternativas[0].avisos == []
