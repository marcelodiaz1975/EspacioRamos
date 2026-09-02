import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.llaves import (
    agregar_acceso_llave,
    asignar_llave,
    crear_llave,
    devolver_llave,
    ingresar_copias,
    registrar_perdida,
    resumen_stock,
    siguiente_nombre_llave,
)
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


def test_siguiente_nombre_llave_correlativo_por_letra(conn):
    assert siguiente_nombre_llave(conn, "Edificio") == "Tipo llave E1"
    crear_llave(conn, tipo="Edificio")
    assert siguiente_nombre_llave(conn, "Edificio") == "Tipo llave E2"
    assert siguiente_nombre_llave(conn, "Unidad") == "Tipo llave U1"
    crear_llave(conn, tipo="Unidad")
    crear_llave(conn, tipo="Unidad")
    assert siguiente_nombre_llave(conn, "Unidad") == "Tipo llave U3"


def test_crear_llave_asigna_nombre_automatico(conn):
    id_llave = crear_llave(conn, tipo="Edificio", valor_deposito_actual=5000)
    llave = obtener_repositorio(conn, "Llave").obtener(id_llave)
    assert llave["Nombre"] == "Tipo llave E1"
    assert llave["Tipo"] == "Edificio"
    assert llave["ValorDepositoActual"] == pytest.approx(5000)
    assert llave["Activo"] == 1


def test_resumen_stock_vacio(conn):
    id_llave = crear_llave(conn)
    resumen = resumen_stock(conn, id_llave)
    assert resumen == {"ingresadas": 0, "perdidas": 0, "existentes": 0, "asignadas": 0, "disponibles": 0}


def test_ingresar_copias_suma_cantidad(conn):
    id_llave = crear_llave(conn)
    ingresar_copias(conn, id_llave=id_llave, cantidad=3)
    ingresar_copias(conn, id_llave=id_llave, cantidad=2)
    resumen = resumen_stock(conn, id_llave)
    assert resumen["ingresadas"] == 5
    assert resumen["existentes"] == 5
    assert resumen["disponibles"] == 5


def test_ingresar_copias_cantidad_invalida_rechaza(conn):
    id_llave = crear_llave(conn)
    with pytest.raises(ValueError):
        ingresar_copias(conn, id_llave=id_llave, cantidad=0)


def test_asignar_llave_sin_deposito(conn, profesional):
    id_llave = crear_llave(conn, tipo="Unidad")
    ingresar_copias(conn, id_llave=id_llave, cantidad=1)
    id_asignacion = asignar_llave(conn, id_llave=id_llave, id_profesional=profesional, fecha="2026-08-01")

    movimiento = obtener_repositorio(conn, "LlaveMovimiento").obtener(id_asignacion)
    assert movimiento["Fecha"] == "2026-08-01"
    assert movimiento["DepositoCobrado"] == 0
    assert obtener_repositorio(conn, "CargoEspecial").listar() == []


def test_asignar_llave_con_deposito_genera_cargo_especial(conn, profesional):
    id_llave = crear_llave(conn, tipo="Edificio", valor_deposito_actual=5000)
    ingresar_copias(conn, id_llave=id_llave, cantidad=1)
    asignar_llave(conn, id_llave=id_llave, id_profesional=profesional, cobrar_deposito=True)

    cargos = obtener_repositorio(conn, "CargoEspecial").listar(IdProfesional=profesional)
    assert len(cargos) == 1
    assert cargos[0]["Tipo"] == "Débito"
    assert cargos[0]["Monto"] == pytest.approx(5000)
    assert cargos[0]["IdLlave"] == id_llave


def test_asignar_llave_con_deposito_manual_distinto_al_default(conn, profesional):
    id_llave = crear_llave(conn, valor_deposito_actual=5000)
    ingresar_copias(conn, id_llave=id_llave, cantidad=1)
    asignar_llave(conn, id_llave=id_llave, id_profesional=profesional, cobrar_deposito=True, monto_cobrado=3000)

    cargos = obtener_repositorio(conn, "CargoEspecial").listar(IdProfesional=profesional)
    assert cargos[0]["Monto"] == pytest.approx(3000)


def test_no_se_puede_asignar_sin_copias_disponibles(conn, profesional):
    id_llave = crear_llave(conn)
    ingresar_copias(conn, id_llave=id_llave, cantidad=1)
    otro_profesional = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Gomez")
    asignar_llave(conn, id_llave=id_llave, id_profesional=profesional)

    with pytest.raises(ValueError):
        asignar_llave(conn, id_llave=id_llave, id_profesional=otro_profesional)


def test_dos_asignaciones_simultaneas_del_mismo_tipo_a_distintos_profesionales(conn, profesional):
    """El motivo entero de separar Tipo de llave y stock: la clienta
    reparte varias copias del mismo tipo (ej. la llave que abre un
    edificio entero) entre distintos profesionales al mismo tiempo."""
    id_llave = crear_llave(conn, tipo="Edificio")
    ingresar_copias(conn, id_llave=id_llave, cantidad=2)
    otro_profesional = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Gomez")

    asignar_llave(conn, id_llave=id_llave, id_profesional=profesional)
    id_asignacion_2 = asignar_llave(conn, id_llave=id_llave, id_profesional=otro_profesional)

    assert id_asignacion_2 is not None
    resumen = resumen_stock(conn, id_llave)
    assert resumen["asignadas"] == 2
    assert resumen["disponibles"] == 0


def test_se_puede_reasignar_luego_de_devuelta(conn, profesional):
    id_llave = crear_llave(conn)
    ingresar_copias(conn, id_llave=id_llave, cantidad=1)
    otro_profesional = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Gomez")
    id_asignacion = asignar_llave(conn, id_llave=id_llave, id_profesional=profesional)
    devolver_llave(conn, id_asignacion, fecha="2026-08-10")

    id_asignacion_2 = asignar_llave(conn, id_llave=id_llave, id_profesional=otro_profesional)
    assert id_asignacion_2 is not None


def test_asignar_llave_inexistente_rechaza(conn, profesional):
    with pytest.raises(ValueError):
        asignar_llave(conn, id_llave=999, id_profesional=profesional)


def test_devolver_llave_con_reintegro_genera_cargo_especial_credito(conn, profesional):
    id_llave = crear_llave(conn, valor_deposito_actual=5000)
    ingresar_copias(conn, id_llave=id_llave, cantidad=1)
    id_asignacion = asignar_llave(conn, id_llave=id_llave, id_profesional=profesional, cobrar_deposito=True)

    devolver_llave(conn, id_asignacion, fecha="2026-08-15", reintegrar_deposito=True)

    cargos = obtener_repositorio(conn, "CargoEspecial").listar(IdProfesional=profesional)
    assert len(cargos) == 2
    credito, debito = sorted(cargos, key=lambda c: c["Tipo"])
    assert credito["Tipo"] == "Crédito"
    assert credito["Monto"] == pytest.approx(-5000)
    assert debito["Tipo"] == "Débito"

    resumen = resumen_stock(conn, id_llave)
    assert resumen["asignadas"] == 0
    assert resumen["disponibles"] == 1


def test_devolver_llave_sin_reintegro_no_genera_cargo(conn, profesional):
    id_llave = crear_llave(conn)
    ingresar_copias(conn, id_llave=id_llave, cantidad=1)
    id_asignacion = asignar_llave(conn, id_llave=id_llave, id_profesional=profesional)
    devolver_llave(conn, id_asignacion, fecha="2026-08-15")

    assert obtener_repositorio(conn, "CargoEspecial").listar() == []


def test_devolver_asignacion_ya_cerrada_falla(conn, profesional):
    id_llave = crear_llave(conn)
    ingresar_copias(conn, id_llave=id_llave, cantidad=1)
    id_asignacion = asignar_llave(conn, id_llave=id_llave, id_profesional=profesional)
    devolver_llave(conn, id_asignacion, fecha="2026-08-15")

    with pytest.raises(ValueError):
        devolver_llave(conn, id_asignacion, fecha="2026-08-20")


def test_registrar_perdida_no_reintegra_y_deposito_queda_perdido(conn, profesional):
    id_llave = crear_llave(conn, valor_deposito_actual=5000)
    ingresar_copias(conn, id_llave=id_llave, cantidad=1)
    id_asignacion = asignar_llave(conn, id_llave=id_llave, id_profesional=profesional, cobrar_deposito=True)

    registrar_perdida(conn, id_asignacion=id_asignacion, fecha="2026-08-20")

    cargos = obtener_repositorio(conn, "CargoEspecial").listar(IdProfesional=profesional)
    assert len(cargos) == 1  # solo el débito original, ningún crédito de reintegro
    assert cargos[0]["Tipo"] == "Débito"

    resumen = resumen_stock(conn, id_llave)
    assert resumen["perdidas"] == 1
    assert resumen["existentes"] == 0
    assert resumen["asignadas"] == 0
    assert resumen["disponibles"] == 0


def test_registrar_perdida_permite_reasignar_pagando_deposito_de_nuevo(conn, profesional):
    """Si se le da una copia nueva después de perder la anterior, es una
    asignación nueva e independiente que vuelve a cobrar depósito."""
    id_llave = crear_llave(conn, valor_deposito_actual=5000)
    ingresar_copias(conn, id_llave=id_llave, cantidad=1)
    id_asignacion = asignar_llave(conn, id_llave=id_llave, id_profesional=profesional, cobrar_deposito=True)
    registrar_perdida(conn, id_asignacion=id_asignacion)

    ingresar_copias(conn, id_llave=id_llave, cantidad=1)
    asignar_llave(conn, id_llave=id_llave, id_profesional=profesional, cobrar_deposito=True)

    cargos = obtener_repositorio(conn, "CargoEspecial").listar(IdProfesional=profesional, Tipo="Débito")
    assert len(cargos) == 2


def test_registrar_perdida_de_asignacion_ya_cerrada_falla(conn, profesional):
    id_llave = crear_llave(conn)
    ingresar_copias(conn, id_llave=id_llave, cantidad=1)
    id_asignacion = asignar_llave(conn, id_llave=id_llave, id_profesional=profesional)
    devolver_llave(conn, id_asignacion)

    with pytest.raises(ValueError):
        registrar_perdida(conn, id_asignacion=id_asignacion)


def test_registrar_perdida_de_stock_sin_asignar(conn):
    """Copias que se pierden/traspapelan antes de ser asignadas a nadie
    (ej. en el cajón) — sin profesional ni depósito involucrado."""
    id_llave = crear_llave(conn, valor_deposito_actual=5000)
    ingresar_copias(conn, id_llave=id_llave, cantidad=3)

    registrar_perdida(conn, id_llave=id_llave, cantidad=2)

    resumen = resumen_stock(conn, id_llave)
    assert resumen["perdidas"] == 2
    assert resumen["existentes"] == 1
    assert resumen["disponibles"] == 1
    assert obtener_repositorio(conn, "CargoEspecial").listar() == []


def test_registrar_perdida_de_stock_sin_cantidad_disponible_rechaza(conn):
    id_llave = crear_llave(conn)
    ingresar_copias(conn, id_llave=id_llave, cantidad=1)

    with pytest.raises(ValueError):
        registrar_perdida(conn, id_llave=id_llave, cantidad=2)


def test_registrar_perdida_sin_id_asignacion_ni_id_llave_rechaza(conn):
    with pytest.raises(ValueError):
        registrar_perdida(conn)


def test_concepto_deposito_llave_tipo_edificio(conn, profesional, edificios):
    id_edificio_1, _ = edificios
    id_llave = crear_llave(conn, tipo="Edificio", valor_deposito_actual=5000)
    agregar_acceso_llave(conn, id_llave=id_llave, id_edificio=id_edificio_1)
    ingresar_copias(conn, id_llave=id_llave, cantidad=1)

    asignar_llave(conn, id_llave=id_llave, id_profesional=profesional, cobrar_deposito=True)

    cargo = obtener_repositorio(conn, "CargoEspecial").listar(IdProfesional=profesional)[0]
    assert cargo["Concepto"] == "Depósito llave edificio Ramos 1"


def test_concepto_deposito_y_reintegro_llave_tipo_unidad_con_un_solo_acceso(conn, profesional, edificios):
    id_edificio_1, _ = edificios
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio_1, Departamento='7mo "L"')
    id_llave = crear_llave(conn, tipo="Unidad", valor_deposito_actual=3000)
    agregar_acceso_llave(conn, id_llave=id_llave, id_edificio=id_edificio_1, id_unidad=id_unidad)
    ingresar_copias(conn, id_llave=id_llave, cantidad=1)

    id_asignacion = asignar_llave(conn, id_llave=id_llave, id_profesional=profesional, cobrar_deposito=True)
    devolver_llave(conn, id_asignacion, reintegrar_deposito=True)

    cargos = obtener_repositorio(conn, "CargoEspecial").listar(IdProfesional=profesional)
    debito = next(c for c in cargos if c["Tipo"] == "Débito")
    credito = next(c for c in cargos if c["Tipo"] == "Crédito")
    assert debito["Concepto"] == 'Depósito llave unidad del 7mo "L" del edificio Ramos 1'
    assert credito["Concepto"] == 'Reintegro depósito llave unidad del 7mo "L" del edificio Ramos 1'


def test_concepto_llave_tipo_unidad_con_varios_accesos_queda_generico(conn, profesional, edificios):
    """Una llave que abre más de una unidad a la vez (cerradura gemela,
    del mismo edificio o de otro) no se puede nombrar sin ambigüedad, así
    que el concepto queda genérico."""
    id_edificio_1, id_edificio_2 = edificios
    id_unidad_1 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio_1, Departamento='EP "K"')
    id_unidad_2 = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio_2, Departamento='5to "G"')
    id_llave = crear_llave(conn, tipo="Unidad", valor_deposito_actual=3000)
    agregar_acceso_llave(conn, id_llave=id_llave, id_edificio=id_edificio_1, id_unidad=id_unidad_1)
    agregar_acceso_llave(conn, id_llave=id_llave, id_edificio=id_edificio_2, id_unidad=id_unidad_2)
    ingresar_copias(conn, id_llave=id_llave, cantidad=1)

    asignar_llave(conn, id_llave=id_llave, id_profesional=profesional, cobrar_deposito=True)

    cargo = obtener_repositorio(conn, "CargoEspecial").listar(IdProfesional=profesional)[0]
    assert cargo["Concepto"] == "Depósito llave unidad"


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
