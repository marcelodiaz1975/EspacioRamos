import json

import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


def test_bloques_rigidos_por_defecto(conn):
    bloques = obtener_repositorio(conn, "BloqueRigido").listar()
    assert len(bloques) == 2
    horarios = {(b["HoraInicio"], b["HoraFin"]) for b in bloques}
    assert horarios == {(9, 11), (18, 21)}
    bloque_18 = next(b for b in bloques if b["HoraInicio"] == 18)
    assert json.loads(bloque_18["DiasLogica"]) == ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]
    assert "Sábado" in json.loads(bloque_18["DiasVisualizacion"])


def test_configuracion_por_defecto(conn):
    cfg = obtener_repositorio(conn, "Configuracion").obtener(1)
    assert cfg["HoraInicioGrilla"] == 8
    assert cfg["HoraFinGrilla"] == 22


def test_profesiones_por_defecto(conn):
    profesiones = obtener_repositorio(conn, "Profesion").listar()
    assert len(profesiones) == 12
    nombres = {p["Nombre"] for p in profesiones}
    assert "Psicología" in nombres
    assert "Nutrición" in nombres


def test_fonoaudiologia_y_psicopedagogia_tienen_desplegable_de_tratamiento(conn):
    """Sección 8.1: son las dos únicas profesiones con "(desplegable)" —
    el resto tiene un único tratamiento por defecto, sin opciones."""
    repo = obtener_repositorio(conn, "Profesion")
    fono = repo.listar(Nombre="Fonoaudiología")[0]
    psp = repo.listar(Nombre="Psicopedagogía")[0]
    psico = repo.listar(Nombre="Psicología")[0]

    assert fono["TieneMultiplesTratamientos"] == 1
    assert fono["OpcionesTratamientoMasculino"] == "Fgo.,Lic."
    assert fono["OpcionesTratamientoFemenino"] == "Fga.,Lic."
    assert psp["TieneMultiplesTratamientos"] == 1
    assert psp["OpcionesTratamientoMasculino"] == "Psp.,Lic."
    assert psico["TieneMultiplesTratamientos"] == 0
    assert psico["OpcionesTratamientoMasculino"] is None


def test_esquema_descuentos_tope_25(conn):
    tramos = obtener_repositorio(conn, "EsquemaDescuentos").listar()
    assert max(t["PorcentajeDescuento"] for t in tramos) == 25


def test_sembrar_es_idempotente(conn):
    sembrar_valores_por_defecto(conn)
    assert len(obtener_repositorio(conn, "BloqueRigido").listar()) == 2
    assert len(obtener_repositorio(conn, "Profesion").listar()) == 12


def test_condiciones_normas_por_defecto(conn):
    condiciones = obtener_repositorio(conn, "CondicionNorma").listar()
    assert len(condiciones) == 21
    numeros = sorted(c["Numero"] for c in condiciones)
    assert numeros == list(range(1, 22))
    primera = next(c for c in condiciones if c["Numero"] == 1)
    assert primera["Titulo"] == "Forma de pago"
    ultima = next(c for c in condiciones if c["Numero"] == 21)
    assert ultima["Titulo"] == "Conformidad y cumplimiento"
    assert all(c["Activo"] == 1 for c in condiciones)
