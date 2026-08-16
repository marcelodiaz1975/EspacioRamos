from datetime import date

import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.archivos_generados import (
    aplicar_cambio_codigo,
    carpeta_archivos_varios,
    carpeta_base,
    carpeta_documentacion_profesional,
    carpeta_imagenes,
    carpeta_profesional,
    destino_sin_colision,
    limpiar_liquidaciones_antiguas,
    renombrar_carpeta_profesional,
    vaciar_carpeta,
)
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


def _configurar_carpeta_base(conn, ruta) -> None:
    obtener_repositorio(conn, "Configuracion").actualizar(1, CarpetaBaseArchivos=str(ruta))


def test_carpeta_base_none_sin_configurar(conn):
    assert carpeta_base(conn) is None


def test_carpeta_archivos_varios_falla_sin_carpeta_base(conn):
    with pytest.raises(ValueError):
        carpeta_archivos_varios(conn, "Propuesta")


def test_carpeta_archivos_varios_crea_subcarpeta(conn, tmp_path):
    _configurar_carpeta_base(conn, tmp_path)
    carpeta = carpeta_archivos_varios(conn, "Propuesta")
    assert carpeta == tmp_path / "Archivos varios" / "Propuesta"
    assert carpeta.is_dir()


def test_carpeta_profesional_crea_subcarpeta(conn, tmp_path):
    _configurar_carpeta_base(conn, tmp_path)
    carpeta = carpeta_profesional(conn, "R1")
    assert carpeta == tmp_path / "Profesionales" / "R1"
    assert carpeta.is_dir()


def test_carpeta_profesional_sin_codigo_falla(conn, tmp_path):
    _configurar_carpeta_base(conn, tmp_path)
    with pytest.raises(ValueError):
        carpeta_profesional(conn, "")


def test_vaciar_carpeta_borra_solo_archivos_sueltos(tmp_path):
    (tmp_path / "a.pdf").write_text("x")
    (tmp_path / "b.pdf").write_text("x")
    subcarpeta = tmp_path / "sub"
    subcarpeta.mkdir()

    borrados = vaciar_carpeta(tmp_path)

    assert borrados == 2
    assert not (tmp_path / "a.pdf").exists()
    assert subcarpeta.exists()


def test_vaciar_carpeta_inexistente_no_falla(tmp_path):
    assert vaciar_carpeta(tmp_path / "no-existe") == 0


def test_limpiar_liquidaciones_antiguas_borra_mas_de_un_anio(tmp_path):
    (tmp_path / "2025-01 - Liquidación Juan Perez.pdf").write_text("x")
    (tmp_path / "2026-08 - Liquidación Juan Perez.pdf").write_text("x")

    borrados = limpiar_liquidaciones_antiguas(tmp_path, date(2026, 8, 15))

    assert borrados == 1
    assert not (tmp_path / "2025-01 - Liquidación Juan Perez.pdf").exists()
    assert (tmp_path / "2026-08 - Liquidación Juan Perez.pdf").exists()


def test_renombrar_carpeta_profesional_conserva_archivos(conn, tmp_path):
    _configurar_carpeta_base(conn, tmp_path)
    carpeta_r1 = carpeta_profesional(conn, "R1")
    (carpeta_r1 / "2026-08 - Liquidación Juan Perez.pdf").write_text("x")

    renombrar_carpeta_profesional(conn, "R1", "X34")

    carpeta_x34 = tmp_path / "Profesionales" / "X34"
    assert carpeta_x34.is_dir()
    assert (carpeta_x34 / "2026-08 - Liquidación Juan Perez.pdf").exists()
    assert not carpeta_r1.exists()


def test_aplicar_cambio_codigo_registra_historial_y_renombra_carpeta(conn, tmp_path):
    _configurar_carpeta_base(conn, tmp_path)
    repo = obtener_repositorio(conn, "Profesional")
    id_prof = repo.crear(CategoriaProfesional="R", Apellido="Ramos", IdCodigo="R3")
    carpeta_r3 = carpeta_profesional(conn, "R3")
    (carpeta_r3 / "2026-08 - Liquidación Ramos.pdf").write_text("x")  # reciente: se conserva
    (carpeta_r3 / "2025-01 - Liquidación Ramos.pdf").write_text("x")  # +1 año: se limpia en el mismo proceso
    registro_anterior = repo.obtener(id_prof)

    repo.actualizar(id_prof, CategoriaProfesional="X", IdCodigo="X34")
    aplicar_cambio_codigo(
        conn, registro_anterior, {"CategoriaProfesional": "X", "IdCodigo": "X34"}, date(2026, 8, 15),
    )

    historial = conn.execute("SELECT * FROM HistorialCodigo WHERE IdProfesional = ?", (id_prof,)).fetchone()
    assert historial["CategoriaAnterior"] == "R"
    assert historial["CodigoAnterior"] == "R3"
    assert historial["CategoriaNueva"] == "X"
    assert historial["CodigoNuevo"] == "X34"

    carpeta_nueva = tmp_path / "Profesionales" / "X34"
    assert (carpeta_nueva / "2026-08 - Liquidación Ramos.pdf").exists()
    assert not (carpeta_nueva / "2025-01 - Liquidación Ramos.pdf").exists()
    assert not (tmp_path / "Profesionales" / "R3").exists()


def test_aplicar_cambio_codigo_sin_cambios_no_hace_nada(conn, tmp_path):
    _configurar_carpeta_base(conn, tmp_path)
    repo = obtener_repositorio(conn, "Profesional")
    id_prof = repo.crear(CategoriaProfesional="R", Apellido="Ramos", IdCodigo="R3")
    registro = repo.obtener(id_prof)

    aplicar_cambio_codigo(conn, registro, {"CategoriaProfesional": "R", "IdCodigo": "R3"}, date(2026, 8, 15))

    assert conn.execute("SELECT COUNT(*) FROM HistorialCodigo").fetchone()[0] == 0


def test_carpeta_documentacion_profesional_crea_subcarpeta(conn, tmp_path):
    _configurar_carpeta_base(conn, tmp_path)
    carpeta = carpeta_documentacion_profesional(conn, "R1")
    assert carpeta == tmp_path / "Profesionales" / "R1" / "Documentación"
    assert carpeta.is_dir()


def test_carpeta_imagenes_crea_subcarpeta_por_id(conn, tmp_path):
    _configurar_carpeta_base(conn, tmp_path)
    carpeta = carpeta_imagenes(conn, "Consultorio", 7)
    assert carpeta == tmp_path / "Imagenes" / "Consultorio_7"
    assert carpeta.is_dir()


def test_destino_sin_colision_devuelve_nombre_original_si_no_existe(tmp_path):
    assert destino_sin_colision(tmp_path, "foto.jpg") == tmp_path / "foto.jpg"


def test_destino_sin_colision_agrega_sufijo_si_ya_existe(tmp_path):
    (tmp_path / "foto.jpg").write_text("x")
    assert destino_sin_colision(tmp_path, "foto.jpg") == tmp_path / "foto (2).jpg"
    (tmp_path / "foto (2).jpg").write_text("x")
    assert destino_sin_colision(tmp_path, "foto.jpg") == tmp_path / "foto (3).jpg"


def test_renombrar_carpeta_profesional_conserva_la_subcarpeta_documentacion(conn, tmp_path):
    _configurar_carpeta_base(conn, tmp_path)
    carpeta_documentacion_profesional(conn, "R3")  # crea Profesionales/R3/Documentación
    (tmp_path / "Profesionales" / "R3" / "Documentación" / "dni.pdf").write_text("x")

    renombrar_carpeta_profesional(conn, "R3", "X34")

    assert (tmp_path / "Profesionales" / "X34" / "Documentación" / "dni.pdf").exists()
    assert not (tmp_path / "Profesionales" / "R3").exists()
