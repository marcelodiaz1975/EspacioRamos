import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.llaves import crear_llave, devolver_llave, entregar_llave
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


@pytest.fixture
def profesional(conn):
    return obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Lo Veci")


def test_entregar_llave_sin_deposito(conn, profesional):
    id_llave = crear_llave(conn, descripcion="Llave unidad 7mo L", tipo="Unidad")
    id_entrega = entregar_llave(conn, id_llave=id_llave, id_profesional=profesional, fecha_entrega="2026-08-01")

    tenencia = obtener_repositorio(conn, "LlaveProfesional").obtener(id_entrega)
    assert tenencia["FechaEntrega"] == "2026-08-01"
    assert tenencia["DepositoCobrado"] == 0
    assert obtener_repositorio(conn, "CargoEspecial").listar() == []


def test_entregar_llave_con_deposito_genera_cargo_especial(conn, profesional):
    id_llave = crear_llave(conn, descripcion="Llave edificio", tipo="Edificio", valor_deposito_actual=5000)
    entregar_llave(
        conn, id_llave=id_llave, id_profesional=profesional, cobrar_deposito=True, periodo_imputado="2026-08",
    )

    cargos = obtener_repositorio(conn, "CargoEspecial").listar(IdProfesional=profesional)
    assert len(cargos) == 1
    assert cargos[0]["Tipo"] == "Débito"
    assert cargos[0]["Monto"] == pytest.approx(5000)
    assert cargos[0]["IdLlave"] == id_llave


def test_entregar_llave_con_deposito_manual_distinto_al_default(conn, profesional):
    id_llave = crear_llave(conn, valor_deposito_actual=5000)
    entregar_llave(conn, id_llave=id_llave, id_profesional=profesional, cobrar_deposito=True, monto_cobrado=3000)

    cargos = obtener_repositorio(conn, "CargoEspecial").listar(IdProfesional=profesional)
    assert cargos[0]["Monto"] == pytest.approx(3000)


def test_no_se_puede_entregar_llave_con_titular_activo(conn, profesional):
    id_llave = crear_llave(conn)
    otro_profesional = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Gomez")
    entregar_llave(conn, id_llave=id_llave, id_profesional=profesional)

    with pytest.raises(ValueError):
        entregar_llave(conn, id_llave=id_llave, id_profesional=otro_profesional)


def test_se_puede_reentregar_llave_luego_de_devuelta(conn, profesional):
    id_llave = crear_llave(conn)
    otro_profesional = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Gomez")
    id_entrega = entregar_llave(conn, id_llave=id_llave, id_profesional=profesional)
    devolver_llave(conn, id_entrega, fecha_devolucion="2026-08-10")

    id_entrega_2 = entregar_llave(conn, id_llave=id_llave, id_profesional=otro_profesional)
    assert id_entrega_2 is not None


def test_devolver_llave_con_reintegro_genera_cargo_especial_credito(conn, profesional):
    id_llave = crear_llave(conn, valor_deposito_actual=5000)
    id_entrega = entregar_llave(conn, id_llave=id_llave, id_profesional=profesional, cobrar_deposito=True)

    devolver_llave(
        conn, id_entrega, fecha_devolucion="2026-08-15", reintegrar_deposito=True, periodo_imputado="2026-08",
    )

    cargos = obtener_repositorio(conn, "CargoEspecial").listar(IdProfesional=profesional)
    assert len(cargos) == 2
    credito, debito = sorted(cargos, key=lambda c: c["Tipo"])
    assert credito["Tipo"] == "Crédito"
    assert credito["Monto"] == pytest.approx(5000)
    assert debito["Tipo"] == "Débito"

    tenencia = obtener_repositorio(conn, "LlaveProfesional").obtener(id_entrega)
    assert tenencia["FechaDevolucion"] == "2026-08-15"
    assert tenencia["DepositoReintegrado"] == 1


def test_devolver_llave_sin_reintegro_no_genera_cargo(conn, profesional):
    id_llave = crear_llave(conn)
    id_entrega = entregar_llave(conn, id_llave=id_llave, id_profesional=profesional)
    devolver_llave(conn, id_entrega, fecha_devolucion="2026-08-15")

    assert obtener_repositorio(conn, "CargoEspecial").listar() == []


def test_devolver_llave_ya_devuelta_falla(conn, profesional):
    id_llave = crear_llave(conn)
    id_entrega = entregar_llave(conn, id_llave=id_llave, id_profesional=profesional)
    devolver_llave(conn, id_entrega, fecha_devolucion="2026-08-15")

    with pytest.raises(ValueError):
        devolver_llave(conn, id_entrega, fecha_devolucion="2026-08-20")
