import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.llaves import agregar_acceso_llave, crear_copia_llave, crear_llave, devolver_llave, entregar_llave
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


@pytest.fixture
def edificios(conn):
    repo = obtener_repositorio(conn, "Edificio")
    return (
        repo.crear(Nombre="Ramos 1", Domicilio="Av. Rivadavia 1234", DomicilioLocalidad="CABA"),
        repo.crear(Nombre="Ramos 2", Domicilio="Av. Rivadavia 5678", DomicilioLocalidad="CABA"),
    )


def test_crear_copia_llave_sugiere_identificador_correlativo(conn):
    id_llave = crear_llave(conn, descripcion="Llave edificio")
    id_copia_1 = crear_copia_llave(conn, id_llave=id_llave)
    id_copia_2 = crear_copia_llave(conn, id_llave=id_llave)

    copia_1 = obtener_repositorio(conn, "LlaveCopia").obtener(id_copia_1)
    copia_2 = obtener_repositorio(conn, "LlaveCopia").obtener(id_copia_2)
    assert copia_1["Identificador"] == "Copia 1"
    assert copia_2["Identificador"] == "Copia 2"


def test_crear_copia_llave_admite_identificador_propio(conn):
    id_llave = crear_llave(conn)
    id_copia = crear_copia_llave(conn, id_llave=id_llave, identificador="Llavero rojo")
    copia = obtener_repositorio(conn, "LlaveCopia").obtener(id_copia)
    assert copia["Identificador"] == "Llavero rojo"


def test_crear_copia_llave_de_tipo_inexistente_rechaza(conn):
    with pytest.raises(ValueError):
        crear_copia_llave(conn, id_llave=999)


def test_entregar_llave_sin_deposito(conn, profesional):
    id_llave = crear_llave(conn, descripcion="Llave unidad 7mo L", tipo="Unidad")
    id_copia = crear_copia_llave(conn, id_llave=id_llave)
    id_entrega = entregar_llave(conn, id_copia=id_copia, id_profesional=profesional, fecha_entrega="2026-08-01")

    tenencia = obtener_repositorio(conn, "LlaveProfesional").obtener(id_entrega)
    assert tenencia["FechaEntrega"] == "2026-08-01"
    assert tenencia["DepositoCobrado"] == 0
    assert obtener_repositorio(conn, "CargoEspecial").listar() == []


def test_entregar_llave_con_deposito_genera_cargo_especial(conn, profesional):
    id_llave = crear_llave(conn, descripcion="Llave edificio", tipo="Edificio", valor_deposito_actual=5000)
    id_copia = crear_copia_llave(conn, id_llave=id_llave)
    entregar_llave(
        conn, id_copia=id_copia, id_profesional=profesional, cobrar_deposito=True, periodo_imputado="2026-08",
    )

    cargos = obtener_repositorio(conn, "CargoEspecial").listar(IdProfesional=profesional)
    assert len(cargos) == 1
    assert cargos[0]["Tipo"] == "Débito"
    assert cargos[0]["Monto"] == pytest.approx(5000)
    assert cargos[0]["IdLlave"] == id_llave


def test_entregar_llave_con_deposito_manual_distinto_al_default(conn, profesional):
    id_llave = crear_llave(conn, valor_deposito_actual=5000)
    id_copia = crear_copia_llave(conn, id_llave=id_llave)
    entregar_llave(conn, id_copia=id_copia, id_profesional=profesional, cobrar_deposito=True, monto_cobrado=3000)

    cargos = obtener_repositorio(conn, "CargoEspecial").listar(IdProfesional=profesional)
    assert cargos[0]["Monto"] == pytest.approx(3000)


def test_no_se_puede_entregar_la_misma_copia_con_titular_activo(conn, profesional):
    id_llave = crear_llave(conn)
    id_copia = crear_copia_llave(conn, id_llave=id_llave)
    otro_profesional = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Gomez")
    entregar_llave(conn, id_copia=id_copia, id_profesional=profesional)

    with pytest.raises(ValueError):
        entregar_llave(conn, id_copia=id_copia, id_profesional=otro_profesional)


def test_dos_copias_del_mismo_tipo_pueden_estar_entregadas_a_la_vez(conn, profesional):
    """El motivo entero de separar tipo de llave y copia física: la
    clienta reparte varias copias del mismo tipo (ej. la llave que abre
    un edificio entero) entre distintos profesionales al mismo tiempo."""
    id_llave = crear_llave(conn, descripcion="Llave edificio", tipo="Edificio")
    id_copia_1 = crear_copia_llave(conn, id_llave=id_llave)
    id_copia_2 = crear_copia_llave(conn, id_llave=id_llave)
    otro_profesional = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Gomez")

    entregar_llave(conn, id_copia=id_copia_1, id_profesional=profesional)
    id_entrega_2 = entregar_llave(conn, id_copia=id_copia_2, id_profesional=otro_profesional)

    assert id_entrega_2 is not None
    tenencias = obtener_repositorio(conn, "LlaveProfesional").listar()
    assert len(tenencias) == 2
    assert {t["IdProfesional"] for t in tenencias} == {profesional, otro_profesional}


def test_se_puede_reentregar_copia_luego_de_devuelta(conn, profesional):
    id_llave = crear_llave(conn)
    id_copia = crear_copia_llave(conn, id_llave=id_llave)
    otro_profesional = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Gomez")
    id_entrega = entregar_llave(conn, id_copia=id_copia, id_profesional=profesional)
    devolver_llave(conn, id_entrega, fecha_devolucion="2026-08-10")

    id_entrega_2 = entregar_llave(conn, id_copia=id_copia, id_profesional=otro_profesional)
    assert id_entrega_2 is not None


def test_entregar_copia_inexistente_rechaza(conn, profesional):
    with pytest.raises(ValueError):
        entregar_llave(conn, id_copia=999, id_profesional=profesional)


def test_devolver_llave_con_reintegro_genera_cargo_especial_credito(conn, profesional):
    id_llave = crear_llave(conn, valor_deposito_actual=5000)
    id_copia = crear_copia_llave(conn, id_llave=id_llave)
    id_entrega = entregar_llave(conn, id_copia=id_copia, id_profesional=profesional, cobrar_deposito=True)

    devolver_llave(
        conn, id_entrega, fecha_devolucion="2026-08-15", reintegrar_deposito=True, periodo_imputado="2026-08",
    )

    cargos = obtener_repositorio(conn, "CargoEspecial").listar(IdProfesional=profesional)
    assert len(cargos) == 2
    credito, debito = sorted(cargos, key=lambda c: c["Tipo"])
    assert credito["Tipo"] == "Crédito"
    assert credito["Monto"] == pytest.approx(-5000)
    assert debito["Tipo"] == "Débito"

    tenencia = obtener_repositorio(conn, "LlaveProfesional").obtener(id_entrega)
    assert tenencia["FechaDevolucion"] == "2026-08-15"
    assert tenencia["DepositoReintegrado"] == 1


def test_devolver_llave_sin_reintegro_no_genera_cargo(conn, profesional):
    id_llave = crear_llave(conn)
    id_copia = crear_copia_llave(conn, id_llave=id_llave)
    id_entrega = entregar_llave(conn, id_copia=id_copia, id_profesional=profesional)
    devolver_llave(conn, id_entrega, fecha_devolucion="2026-08-15")

    assert obtener_repositorio(conn, "CargoEspecial").listar() == []


def test_devolver_llave_ya_devuelta_falla(conn, profesional):
    id_llave = crear_llave(conn)
    id_copia = crear_copia_llave(conn, id_llave=id_llave)
    id_entrega = entregar_llave(conn, id_copia=id_copia, id_profesional=profesional)
    devolver_llave(conn, id_entrega, fecha_devolucion="2026-08-15")

    with pytest.raises(ValueError):
        devolver_llave(conn, id_entrega, fecha_devolucion="2026-08-20")


def test_llave_tipo_edificio_no_puede_tener_acceso_a_dos_edificios_distintos(conn, edificios):
    id_edificio_1, id_edificio_2 = edificios
    id_llave = crear_llave(conn, tipo="Edificio")
    agregar_acceso_llave(conn, id_llave=id_llave, id_edificio=id_edificio_1)

    with pytest.raises(ValueError):
        agregar_acceso_llave(conn, id_llave=id_llave, id_edificio=id_edificio_2)


def test_llave_tipo_edificio_admite_varios_accesos_al_mismo_edificio(conn, edificios):
    id_edificio_1, _ = edificios
    id_unidad_1 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio_1, Departamento='1ro "A"')
    id_unidad_2 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio_1, Departamento='2do "B"')
    id_llave = crear_llave(conn, tipo="Edificio")

    agregar_acceso_llave(conn, id_llave=id_llave, id_edificio=id_edificio_1, id_unidad=id_unidad_1)
    id_acceso_2 = agregar_acceso_llave(conn, id_llave=id_llave, id_edificio=id_edificio_1, id_unidad=id_unidad_2)

    assert id_acceso_2 is not None


def test_llave_tipo_unidad_necesita_una_unidad_puntual(conn, edificios):
    id_edificio_1, _ = edificios
    id_llave = crear_llave(conn, tipo="Unidad")

    with pytest.raises(ValueError):
        agregar_acceso_llave(conn, id_llave=id_llave, id_edificio=id_edificio_1)


def test_llave_tipo_unidad_con_unidad_puntual_se_agrega_bien(conn, edificios):
    id_edificio_1, _ = edificios
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio_1, Departamento='7mo "L"')
    id_llave = crear_llave(conn, tipo="Unidad")

    id_acceso = agregar_acceso_llave(conn, id_llave=id_llave, id_edificio=id_edificio_1, id_unidad=id_unidad)
    assert id_acceso is not None


def test_llave_tipo_no_especificada_no_valida_alcance(conn, edificios):
    id_edificio_1, id_edificio_2 = edificios
    id_llave = crear_llave(conn, tipo="No especificada")

    agregar_acceso_llave(conn, id_llave=id_llave, id_edificio=id_edificio_1)
    id_acceso = agregar_acceso_llave(conn, id_llave=id_llave, id_edificio=id_edificio_2)
    assert id_acceso is not None
