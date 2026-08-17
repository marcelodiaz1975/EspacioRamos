import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.profesionales import normalizar_cuit, opciones_tratamiento, sugerir_codigo, tratamiento_sugerido
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


def _id_profesion(conn, nombre):
    return obtener_repositorio(conn, "Profesion").listar(Nombre=nombre)[0]["IdProfesion"]


# --------------------------------------------------------------- sugerir_codigo

def test_sugerir_codigo_primera_de_la_categoria(conn):
    assert sugerir_codigo(conn, "R") == "R1"


def test_sugerir_codigo_toma_el_mas_bajo_disponible(conn):
    obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Uno", IdCodigo="R1")
    obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Tres", IdCodigo="R3")
    assert sugerir_codigo(conn, "R") == "R2"


def test_sugerir_codigo_no_mezcla_categorias(conn):
    obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Uno", IdCodigo="R1")
    assert sugerir_codigo(conn, "X") == "X1"


def test_sugerir_codigo_ignora_codigos_con_formato_distinto(conn):
    obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Raro", IdCodigo="R-viejo")
    assert sugerir_codigo(conn, "R") == "R1"


# ----------------------------------------------------------- tratamiento_sugerido

def test_tratamiento_sugerido_sin_profesion(conn):
    assert tratamiento_sugerido(conn, None, "Masculino") is None


def test_tratamiento_sugerido_profesion_simple(conn):
    id_psicologia = _id_profesion(conn, "Psicología")
    assert tratamiento_sugerido(conn, id_psicologia, "Masculino") == "Lic."
    assert tratamiento_sugerido(conn, id_psicologia, "Femenino") == "Lic."


def test_tratamiento_sugerido_sin_sexo_no_binario(conn):
    id_psicologia = _id_profesion(conn, "Psicología")
    assert tratamiento_sugerido(conn, id_psicologia, "No binario") is None


def test_tratamiento_sugerido_profesion_con_desplegable_toma_la_primera_opcion(conn):
    id_fono = _id_profesion(conn, "Fonoaudiología")
    assert tratamiento_sugerido(conn, id_fono, "Masculino") == "Fgo."
    assert tratamiento_sugerido(conn, id_fono, "Femenino") == "Fga."


# ------------------------------------------------------------ opciones_tratamiento

def test_opciones_tratamiento_profesion_simple_esta_vacia(conn):
    id_psicologia = _id_profesion(conn, "Psicología")
    assert opciones_tratamiento(conn, id_psicologia, "Masculino") == []


def test_opciones_tratamiento_fonoaudiologia(conn):
    id_fono = _id_profesion(conn, "Fonoaudiología")
    assert opciones_tratamiento(conn, id_fono, "Masculino") == ["Fgo.", "Lic."]
    assert opciones_tratamiento(conn, id_fono, "Femenino") == ["Fga.", "Lic."]


def test_opciones_tratamiento_sin_profesion(conn):
    assert opciones_tratamiento(conn, None, "Masculino") == []


# ----------------------------------------------------------------- normalizar_cuit

def test_normalizar_cuit_quita_guiones():
    assert normalizar_cuit("20-12345678-9") == "20123456789"


def test_normalizar_cuit_quita_espacios():
    assert normalizar_cuit("20 12345678 9") == "20123456789"


def test_normalizar_cuit_sin_guiones_no_cambia():
    assert normalizar_cuit("20123456789") == "20123456789"
