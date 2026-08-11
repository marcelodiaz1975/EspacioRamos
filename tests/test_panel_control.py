import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.panel_control import calcular_alertas, puede_avanzar_mes
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


def _fijar_fecha(conn, fecha_iso):
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = ? WHERE IdConfiguracion = 1", (fecha_iso,)
    )


def test_puede_avanzar_mes_ultimo_dia(conn):
    _fijar_fecha(conn, "2026-08-31")
    assert puede_avanzar_mes(conn) is True


def test_puede_avanzar_mes_primer_dia(conn):
    _fijar_fecha(conn, "2026-09-01")
    assert puede_avanzar_mes(conn) is True


def test_no_puede_avanzar_mes_dia_intermedio(conn):
    _fijar_fecha(conn, "2026-08-15")
    assert puede_avanzar_mes(conn) is False


def test_alertas_vacias_sin_datos(conn):
    alertas = calcular_alertas(conn)
    assert alertas.total == 0


def test_alerta_deuda_regular_respeta_tolerancia(conn):
    obtener_repositorio(conn, "Configuracion").actualizar(1, ToleranciaDeudaDescuento=1000)
    obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="R", Apellido="Bajo saldo", SaldoCuentaAnterior=500,
    )
    obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="R", Apellido="Alto saldo", SaldoCuentaAnterior=5000,
    )
    alertas = calcular_alertas(conn)
    assert len(alertas.deuda_regulares) == 1
    assert alertas.deuda_regulares[0]["Apellido"] == "Alto saldo"


def test_alerta_deuda_aislada_no_tiene_tolerancia(conn):
    obtener_repositorio(conn, "Configuracion").actualizar(1, ToleranciaDeudaDescuento=1000)
    obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="A", Apellido="Debe poco", SaldoCuentaAnterior=1,
    )
    alertas = calcular_alertas(conn)
    assert len(alertas.deuda_aisladas) == 1


def test_alerta_fechas_especiales_proximas_respeta_ventana(conn):
    _fijar_fecha(conn, "2026-08-01")
    obtener_repositorio(conn, "FechasEspeciales").crear(Fecha="2026-08-10", Tipo="Feriado nacional", Activo=1)
    obtener_repositorio(conn, "FechasEspeciales").crear(Fecha="2026-09-30", Tipo="Feriado nacional", Activo=1)
    alertas = calcular_alertas(conn)
    assert len(alertas.fechas_especiales_proximas) == 1


def test_alerta_categoria_x_con_llaves_pendientes(conn):
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="X", Apellido="Inactivo")
    id_llave = obtener_repositorio(conn, "Llave").crear(Descripcion="Llave")
    obtener_repositorio(conn, "LlaveProfesional").crear(
        IdLlave=id_llave, IdProfesional=id_prof, FechaEntrega="2026-01-01",
    )
    alertas = calcular_alertas(conn)
    assert len(alertas.categoria_x_con_llaves_pendientes) == 1
