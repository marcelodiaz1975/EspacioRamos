import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.importacion.informe_integridad import generar_informe_integridad


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


def _crear_consultorio(conn):
    conn.execute("INSERT INTO Edificio (Nombre) VALUES ('Torre Norte')")
    id_edificio = conn.execute("SELECT IdEdificio FROM Edificio").fetchone()["IdEdificio"]
    conn.execute("INSERT INTO Unidad (IdEdificio, Departamento) VALUES (?, '1A')", (id_edificio,))
    id_unidad = conn.execute("SELECT IdUnidad FROM Unidad").fetchone()["IdUnidad"]
    conn.execute("INSERT INTO Consultorio (IdUnidad, NumeroConsultorio) VALUES (?, 1)", (id_unidad,))
    conn.commit()
    return conn.execute("SELECT IdConsultorio FROM Consultorio").fetchone()["IdConsultorio"]


def _crear_profesional(conn, id_codigo, apellido, categoria="R", cabeza_equipo=None):
    conn.execute(
        "INSERT INTO Profesional (CategoriaProfesional, IdCodigo, Apellido, ProfesionalCabezaEquipo) "
        "VALUES (?, ?, ?, ?)",
        (categoria, id_codigo, apellido, cabeza_equipo),
    )
    conn.commit()
    return conn.execute("SELECT IdProfesional FROM Profesional WHERE IdCodigo = ?", (id_codigo,)).fetchone()["IdProfesional"]


def _crear_reserva(conn, id_consultorio, id_profesional, dia="Lunes", desde=9, hasta=12):
    conn.execute(
        "INSERT INTO ReservaRegular (IdProfesional, IdConsultorio, DiaSemana, HoraInicio, HoraFin, VigenciaInicio) "
        "VALUES (?, ?, ?, ?, ?, '2026-01-01')",
        (id_profesional, id_consultorio, dia, desde, hasta),
    )
    conn.commit()


def test_sin_problemas_informe_vacio(conn):
    informe = generar_informe_integridad(conn)
    assert informe.total == 0


def test_detecta_codigo_duplicado(conn):
    _crear_profesional(conn, "R1", "Perez")
    _crear_profesional(conn, "R1", "Gomez")
    informe = generar_informe_integridad(conn)
    assert len(informe.codigos_duplicados) == 1
    assert informe.codigos_duplicados[0].codigo == "R1"
    apellidos = {ap for _, ap in informe.codigos_duplicados[0].profesionales}
    assert apellidos == {"Perez", "Gomez"}


def test_no_marca_codigos_distintos(conn):
    _crear_profesional(conn, "R1", "Perez")
    _crear_profesional(conn, "R2", "Gomez")
    informe = generar_informe_integridad(conn)
    assert informe.codigos_duplicados == []


def test_detecta_reservas_superpuestas_sin_relacion(conn):
    id_consultorio = _crear_consultorio(conn)
    p1 = _crear_profesional(conn, "R1", "Perez")
    p2 = _crear_profesional(conn, "R2", "Gomez")
    _crear_reserva(conn, id_consultorio, p1, desde=9, hasta=14)
    _crear_reserva(conn, id_consultorio, p2, desde=12, hasta=15)

    informe = generar_informe_integridad(conn)
    assert len(informe.reservas_superpuestas) == 1


def test_no_marca_reservas_sin_solapamiento_horario(conn):
    id_consultorio = _crear_consultorio(conn)
    p1 = _crear_profesional(conn, "R1", "Perez")
    p2 = _crear_profesional(conn, "R2", "Gomez")
    _crear_reserva(conn, id_consultorio, p1, desde=9, hasta=12)
    _crear_reserva(conn, id_consultorio, p2, desde=12, hasta=15)  # se tocan, no se superponen

    informe = generar_informe_integridad(conn)
    assert informe.reservas_superpuestas == []


def test_no_marca_reservas_de_equipo_relacionado(conn):
    """Un E y su propio R comparten consultorio con aviso, no bloqueo — misma
    regla que usa la pantalla de Reservas (sección 3.9), no debe listarse
    como problema de integridad."""
    id_consultorio = _crear_consultorio(conn)
    r = _crear_profesional(conn, "R1", "Perez")
    e = _crear_profesional(conn, "E1", "PerezAsistente", categoria="E", cabeza_equipo=r)
    _crear_reserva(conn, id_consultorio, r, desde=9, hasta=14)
    _crear_reserva(conn, id_consultorio, e, desde=10, hasta=13)

    informe = generar_informe_integridad(conn)
    assert informe.reservas_superpuestas == []


def test_no_duplica_el_mismo_par_en_ambos_sentidos(conn):
    id_consultorio = _crear_consultorio(conn)
    p1 = _crear_profesional(conn, "R1", "Perez")
    p2 = _crear_profesional(conn, "R2", "Gomez")
    p3 = _crear_profesional(conn, "R3", "Diaz")
    _crear_reserva(conn, id_consultorio, p1, desde=9, hasta=21)
    _crear_reserva(conn, id_consultorio, p2, desde=10, hasta=14)
    _crear_reserva(conn, id_consultorio, p3, desde=15, hasta=18)

    informe = generar_informe_integridad(conn)
    # p1 se superpone con p2 y con p3 por separado -> 2 pares, sin duplicar
    assert len(informe.reservas_superpuestas) == 2
