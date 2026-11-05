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
    carpeta_liquidaciones_simuladas,
    carpeta_profesional,
    destino_sin_colision,
    limpiar_liquidaciones_antiguas,
    limpiar_liquidaciones_simuladas_antiguas,
    nombre_carpeta_consultorio,
    nombre_carpeta_edificio,
    nombre_carpeta_localidad,
    nombre_carpeta_profesional,
    nombre_carpeta_unidad,
    renombrar_carpeta_imagenes_consultorio,
    renombrar_carpeta_imagenes_edificio,
    renombrar_carpeta_imagenes_localidad,
    renombrar_carpeta_imagenes_unidad,
    renombrar_carpeta_profesional,
    resincronizar_carpetas_imagenes,
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


def test_carpeta_profesional_incluye_el_nombre_cuando_existe_el_registro(conn, tmp_path):
    """Pedido explícito de la clienta: la carpeta pasa de nombrarse solo
    con el código a "{código} - {tratamiento} {nombre} {apellido}", igual
    al formato que ya muestran los selectores de profesional."""
    _configurar_carpeta_base(conn, tmp_path)
    obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="R", IdCodigo="R1", Tratamiento="Lic.", NombrePila="Virginia", Apellido="Lo Veci",
    )
    carpeta = carpeta_profesional(conn, "R1")
    assert carpeta == tmp_path / "Profesionales" / "R1 - Lic. Virginia Lo Veci"
    assert carpeta.is_dir()


def test_nombre_carpeta_profesional_sin_ningun_dato_de_nombre():
    assert nombre_carpeta_profesional("R1", None, None, None) == "R1"


def test_nombre_carpeta_profesional_solo_apellido():
    assert nombre_carpeta_profesional("R1", None, None, "Ramos") == "R1 - Ramos"


def test_nombre_carpeta_profesional_sanea_caracteres_invalidos():
    assert nombre_carpeta_profesional("R1", None, None, 'Pérez / López "Jr"') == "R1 - Pérez _ López _Jr_"


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


def test_carpeta_liquidaciones_simuladas_crea_subcarpeta_unica(conn, tmp_path):
    _configurar_carpeta_base(conn, tmp_path)
    carpeta = carpeta_liquidaciones_simuladas(conn)
    assert carpeta == tmp_path / "Liquidaciones simuladas"
    assert carpeta.is_dir()


def test_limpiar_liquidaciones_simuladas_antiguas_retiene_solo_3_meses(tmp_path):
    (tmp_path / "2026-05 - Liquidación simulada Juan Perez.pdf").write_text("x")
    (tmp_path / "2026-06 - Liquidación simulada Juan Perez.pdf").write_text("x")
    (tmp_path / "2026-09 - Liquidación simulada Juan Perez.pdf").write_text("x")

    borrados = limpiar_liquidaciones_simuladas_antiguas(tmp_path, date(2026, 9, 15))

    assert borrados == 1
    assert not (tmp_path / "2026-05 - Liquidación simulada Juan Perez.pdf").exists()
    assert (tmp_path / "2026-06 - Liquidación simulada Juan Perez.pdf").exists()
    assert (tmp_path / "2026-09 - Liquidación simulada Juan Perez.pdf").exists()


def test_limpiar_liquidaciones_simuladas_antiguas_carpeta_inexistente_no_rompe(tmp_path):
    assert limpiar_liquidaciones_simuladas_antiguas(tmp_path / "no existe", date(2026, 9, 15)) == 0


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

    # Apellido ("Ramos") no cambió en este caso — solo categoría/código —
    # así que la carpeta nueva conserva ese mismo nombre, con el código
    # nuevo (pedido general: "Profesionales/{código} - {tratamiento
    # nombre apellido}", ver `nombre_carpeta_profesional`).
    carpeta_nueva = tmp_path / "Profesionales" / "X34 - Ramos"
    assert (carpeta_nueva / "2026-08 - Liquidación Ramos.pdf").exists()
    assert not (carpeta_nueva / "2025-01 - Liquidación Ramos.pdf").exists()
    assert not (tmp_path / "Profesionales" / "R3 - Ramos").exists()


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


def _crear_localidad(conn, localidad="Ramos Mejia") -> int:
    id_localidad = conn.execute("INSERT INTO Localidad (Localidad) VALUES (?)", (localidad,)).lastrowid
    conn.commit()
    return id_localidad


def _crear_edificio(conn, edificio="Imperio", localidad="Ramos Mejia") -> int:
    id_localidad = _crear_localidad(conn, localidad) if localidad is not None else None
    id_edificio = conn.execute(
        "INSERT INTO Edificio (Nombre, IdLocalidad) VALUES (?, ?)", (edificio, id_localidad),
    ).lastrowid
    conn.commit()
    return id_edificio


def _crear_unidad(conn, edificio="Imperio", unidad="7mo L", localidad="Ramos Mejia") -> int:
    id_edificio = _crear_edificio(conn, edificio, localidad)
    id_unidad = conn.execute(
        "INSERT INTO Unidad (IdEdificio, Departamento) VALUES (?, ?)", (id_edificio, unidad),
    ).lastrowid
    conn.commit()
    return id_unidad


def _crear_consultorio(conn, edificio="Imperio", unidad="7mo L", numero=3, localidad="Ramos Mejia") -> int:
    id_unidad = _crear_unidad(conn, edificio, unidad, localidad)
    id_consultorio = conn.execute(
        "INSERT INTO Consultorio (IdUnidad, NumeroConsultorio) VALUES (?, ?)", (id_unidad, numero),
    ).lastrowid
    conn.commit()
    return id_consultorio


def test_nombre_carpeta_localidad_formato():
    assert nombre_carpeta_localidad("Ramos Mejia") == "Localidad_Ramos Mejia"


def test_nombre_carpeta_edificio_formato():
    assert nombre_carpeta_edificio("Ramos Mejia", "Imperio") == "Edificio_Ramos Mejia_Imperio"


def test_nombre_carpeta_unidad_formato():
    assert nombre_carpeta_unidad("Ramos Mejia", "Imperio", "7mo L") == "Unidad_Ramos Mejia_Imperio_7mo L"


def test_nombre_carpeta_consultorio_formato():
    """Pedido explícito de la clienta: "Consultorio_{Localidad}_
    {Edificio}_{Departamento}_C{Nro de consultorio}", ej.
    "Consultorio_Ramos Mejia_Imperio_7mo L_C3" — cambia el formato con
    guiones de la ronda anterior (sin Localidad) a este, con guion bajo
    y Localidad incluida, para que las cuatro carpetas descriptivas
    sigan el mismo patrón."""
    assert nombre_carpeta_consultorio("Ramos Mejia", "Imperio", "7mo L", 3) == "Consultorio_Ramos Mejia_Imperio_7mo L_C3"


def test_carpeta_imagenes_de_localidad_real_usa_nombre_descriptivo(conn, tmp_path):
    """Pedido explícito de la clienta: "la idea es que se replique el
    formato de ruta [de Consultorio] para otros elementos" —
    Localidad/Edificio/Unidad pasan de usar el ID interno a un nombre
    descriptivo, igual que ya tenía Consultorio."""
    _configurar_carpeta_base(conn, tmp_path)
    id_localidad = _crear_localidad(conn)
    carpeta = carpeta_imagenes(conn, "Localidad", id_localidad)
    assert carpeta == tmp_path / "Imagenes" / "Localidad_Ramos Mejia"
    assert carpeta.is_dir()


def test_carpeta_imagenes_de_edificio_real_usa_nombre_descriptivo(conn, tmp_path):
    _configurar_carpeta_base(conn, tmp_path)
    id_edificio = _crear_edificio(conn)
    carpeta = carpeta_imagenes(conn, "Edificio", id_edificio)
    assert carpeta == tmp_path / "Imagenes" / "Edificio_Ramos Mejia_Imperio"
    assert carpeta.is_dir()


def test_carpeta_imagenes_de_edificio_sin_localidad_usa_signo_de_pregunta(conn, tmp_path):
    """"Sin localidad" es una opción válida del catálogo de Edificios
    (`_opciones_localidad`) — sin Localidad de dónde sacar el nombre, el
    nombre de carpeta cae al mismo placeholder "?" que ya usa el resto
    de estos nombres descriptivos para un dato faltante, saneado como
    cualquier otro carácter inválido de carpeta ("?" -> "_", mismo
    criterio que `_CARACTERES_INVALIDOS_CARPETA`)."""
    _configurar_carpeta_base(conn, tmp_path)
    id_edificio = _crear_edificio(conn, localidad=None)
    carpeta = carpeta_imagenes(conn, "Edificio", id_edificio)
    assert carpeta == tmp_path / "Imagenes" / "Edificio___Imperio"


def test_carpeta_imagenes_de_unidad_real_usa_nombre_descriptivo(conn, tmp_path):
    _configurar_carpeta_base(conn, tmp_path)
    id_unidad = _crear_unidad(conn)
    carpeta = carpeta_imagenes(conn, "Unidad", id_unidad)
    assert carpeta == tmp_path / "Imagenes" / "Unidad_Ramos Mejia_Imperio_7mo L"
    assert carpeta.is_dir()


def test_carpeta_imagenes_de_consultorio_real_usa_nombre_descriptivo(conn, tmp_path):
    """Pedido explícito de la clienta: la carpeta de imágenes de un
    consultorio se identifica por Localidad/Edificio/Unidad/Número en
    vez de solo el ID interno."""
    _configurar_carpeta_base(conn, tmp_path)
    id_consultorio = _crear_consultorio(conn)
    carpeta = carpeta_imagenes(conn, "Consultorio", id_consultorio)
    assert carpeta == tmp_path / "Imagenes" / "Consultorio_Ramos Mejia_Imperio_7mo L_C3"
    assert carpeta.is_dir()


@pytest.mark.parametrize(
    "alcance, crear, nombre_nuevo",
    [
        ("Localidad", lambda conn: _crear_localidad(conn), "Localidad_Ramos Mejia"),
        ("Edificio", lambda conn: _crear_edificio(conn), "Edificio_Ramos Mejia_Imperio"),
        ("Unidad", lambda conn: _crear_unidad(conn), "Unidad_Ramos Mejia_Imperio_7mo L"),
        ("Consultorio", lambda conn: _crear_consultorio(conn), "Consultorio_Ramos Mejia_Imperio_7mo L_C3"),
    ],
)
def test_carpeta_imagenes_migra_sola_la_carpeta_vieja_basada_en_id(conn, tmp_path, alcance, crear, nombre_nuevo):
    """Responde la consulta de la clienta ("¿el sistema puede renombrar
    lo existente o lo tengo que hacer manualmente?"): sí, solo —
    cualquier acceso a las imágenes de un registro que todavía tenga la
    carpeta vieja "{Alcance}_{id}" (de antes de este cambio) la migra
    sola al nombre descriptivo, sin perder los archivos ya cargados —
    para los cuatro alcances, no solo Consultorio."""
    _configurar_carpeta_base(conn, tmp_path)
    id_valor = crear(conn)
    carpeta_vieja = tmp_path / "Imagenes" / f"{alcance}_{id_valor}"
    carpeta_vieja.mkdir(parents=True)
    (carpeta_vieja / "foto.jpg").write_text("x")

    carpeta = carpeta_imagenes(conn, alcance, id_valor)

    assert carpeta == tmp_path / "Imagenes" / nombre_nuevo
    assert (carpeta / "foto.jpg").exists()
    assert not carpeta_vieja.exists()


def test_carpeta_imagenes_consultorio_migra_sola_el_formato_anterior_con_guiones(conn, tmp_path):
    """El formato descriptivo de Consultorio ya había cambiado una vez
    antes (de "Consultorio_{id}" a "Consultorio - {Edificio} - {Unidad}
    - {Número}", sin Localidad) — un acceso a las imágenes de un
    consultorio que todavía tenga esa carpeta INTERMEDIA (no la más
    vieja basada en ID) también se migra sola al nombre nuevo."""
    _configurar_carpeta_base(conn, tmp_path)
    id_consultorio = _crear_consultorio(conn)
    carpeta_vieja = tmp_path / "Imagenes" / "Consultorio - Imperio - 7mo L - 3"
    carpeta_vieja.mkdir(parents=True)
    (carpeta_vieja / "foto.jpg").write_text("x")

    carpeta = carpeta_imagenes(conn, "Consultorio", id_consultorio)

    assert carpeta == tmp_path / "Imagenes" / "Consultorio_Ramos Mejia_Imperio_7mo L_C3"
    assert (carpeta / "foto.jpg").exists()
    assert not carpeta_vieja.exists()


def test_carpeta_imagenes_consultorio_sin_registro_sigue_usando_el_id(conn, tmp_path):
    """Un consultorio que ya no existe en la base (eliminado) no tiene
    Localidad/Edificio/Unidad de dónde sacar un nombre descriptivo —
    cae al esquema viejo por ID en vez de romper."""
    _configurar_carpeta_base(conn, tmp_path)
    carpeta = carpeta_imagenes(conn, "Consultorio", 999)
    assert carpeta == tmp_path / "Imagenes" / "Consultorio_999"


def test_resincronizar_carpetas_imagenes_migra_los_cuatro_alcances_de_una(conn, tmp_path):
    """Pedido explícito de la clienta ("tengo las carpetas de imágenes de
    los consultorios con el formato viejo, ¿cómo hago para pasarlas al
    nuevo formato de una manera sencilla?"): no hace falta entrar
    registro por registro — `resincronizar_carpetas_imagenes` encuentra
    y migra sola todas las carpetas viejas basadas en ID, para los cuatro
    alcances a la vez."""
    _configurar_carpeta_base(conn, tmp_path)
    id_localidad = _crear_localidad(conn)
    id_edificio = _crear_edificio(conn)
    id_unidad = _crear_unidad(conn)
    id_consultorio = _crear_consultorio(conn)
    carpetas_viejas = {
        "Localidad": tmp_path / "Imagenes" / f"Localidad_{id_localidad}",
        "Edificio": tmp_path / "Imagenes" / f"Edificio_{id_edificio}",
        "Unidad": tmp_path / "Imagenes" / f"Unidad_{id_unidad}",
        "Consultorio": tmp_path / "Imagenes" / f"Consultorio_{id_consultorio}",
    }
    for carpeta_vieja in carpetas_viejas.values():
        carpeta_vieja.mkdir(parents=True)
        (carpeta_vieja / "foto.jpg").write_text("x")

    migradas = resincronizar_carpetas_imagenes(conn)

    assert migradas == 4
    assert (tmp_path / "Imagenes" / "Localidad_Ramos Mejia" / "foto.jpg").exists()
    assert (tmp_path / "Imagenes" / "Edificio_Ramos Mejia_Imperio" / "foto.jpg").exists()
    assert (tmp_path / "Imagenes" / "Unidad_Ramos Mejia_Imperio_7mo L" / "foto.jpg").exists()
    assert (tmp_path / "Imagenes" / "Consultorio_Ramos Mejia_Imperio_7mo L_C3" / "foto.jpg").exists()
    for carpeta_vieja in carpetas_viejas.values():
        assert not carpeta_vieja.exists()


def test_resincronizar_carpetas_imagenes_migra_el_formato_anterior_con_guiones(conn, tmp_path):
    _configurar_carpeta_base(conn, tmp_path)
    id_consultorio = _crear_consultorio(conn)
    carpeta_vieja = tmp_path / "Imagenes" / "Consultorio - Imperio - 7mo L - 3"
    carpeta_vieja.mkdir(parents=True)
    (carpeta_vieja / "foto.jpg").write_text("x")

    migradas = resincronizar_carpetas_imagenes(conn)

    assert migradas == 1
    assert (tmp_path / "Imagenes" / "Consultorio_Ramos Mejia_Imperio_7mo L_C3" / "foto.jpg").exists()
    assert not carpeta_vieja.exists()
    assert id_consultorio  # usado solo para crear el registro


def test_resincronizar_carpetas_imagenes_no_crea_carpetas_vacias(conn, tmp_path):
    """Un registro que nunca tuvo imágenes cargadas no tiene ninguna
    carpeta vieja en disco — no tiene que terminar con una carpeta nueva
    vacía creada de la nada (a diferencia de llamar a `carpeta_imagenes`
    directo, que siempre crea la carpeta)."""
    _configurar_carpeta_base(conn, tmp_path)
    _crear_consultorio(conn)
    (tmp_path / "Imagenes").mkdir()  # existe la carpeta base de Imagenes, pero vacía

    migradas = resincronizar_carpetas_imagenes(conn)

    assert migradas == 0
    assert list((tmp_path / "Imagenes").iterdir()) == []


def test_resincronizar_carpetas_imagenes_sin_carpeta_base_no_hace_nada(conn):
    assert resincronizar_carpetas_imagenes(conn) == 0


def test_init_database_resincroniza_carpetas_de_imagenes_al_reabrir_la_base(tmp_path):
    """Mismo criterio que `test_pagos.test_init_database_reconcilia_
    saldos_cruzados_ya_cargados_al_reabrir_la_base`: alcanza con reabrir
    la base (sin tocar nada a mano) para que las carpetas viejas queden
    migradas — `init_database` corre la resincronización sola en cada
    arranque."""
    db_path = tmp_path / "test.db"
    conn = init_database(db_path)
    sembrar_valores_por_defecto(conn)
    _configurar_carpeta_base(conn, tmp_path / "base")
    id_consultorio = _crear_consultorio(conn)
    carpeta_vieja = tmp_path / "base" / "Imagenes" / f"Consultorio_{id_consultorio}"
    carpeta_vieja.mkdir(parents=True)
    (carpeta_vieja / "foto.jpg").write_text("x")
    conn.commit()
    conn.close()

    conn = init_database(db_path)  # simula el próximo arranque de la app

    assert (tmp_path / "base" / "Imagenes" / "Consultorio_Ramos Mejia_Imperio_7mo L_C3" / "foto.jpg").exists()
    assert not carpeta_vieja.exists()
    conn.close()


def test_renombrar_carpeta_imagenes_localidad_conserva_archivos(conn, tmp_path):
    _configurar_carpeta_base(conn, tmp_path)
    id_localidad = _crear_localidad(conn, "Ramos Mejia")
    carpeta_vieja = tmp_path / "Imagenes" / "Localidad_Ramos Mejia"
    carpeta_vieja.mkdir(parents=True)
    (carpeta_vieja / "foto.jpg").write_text("x")

    conn.execute("UPDATE Localidad SET Localidad = ? WHERE IdLocalidad = ?", ("Haedo", id_localidad))
    conn.commit()
    renombrar_carpeta_imagenes_localidad(conn, id_localidad, "Localidad_Ramos Mejia")

    carpeta_nueva = tmp_path / "Imagenes" / "Localidad_Haedo"
    assert (carpeta_nueva / "foto.jpg").exists()
    assert not carpeta_vieja.exists()


def test_renombrar_carpeta_imagenes_edificio_conserva_archivos(conn, tmp_path):
    _configurar_carpeta_base(conn, tmp_path)
    id_edificio = _crear_edificio(conn, "Imperio")
    carpeta_vieja = tmp_path / "Imagenes" / "Edificio_Ramos Mejia_Imperio"
    carpeta_vieja.mkdir(parents=True)
    (carpeta_vieja / "foto.jpg").write_text("x")

    conn.execute("UPDATE Edificio SET Nombre = ? WHERE IdEdificio = ?", ("Torre Norte", id_edificio))
    conn.commit()
    renombrar_carpeta_imagenes_edificio(conn, id_edificio, "Edificio_Ramos Mejia_Imperio")

    carpeta_nueva = tmp_path / "Imagenes" / "Edificio_Ramos Mejia_Torre Norte"
    assert (carpeta_nueva / "foto.jpg").exists()
    assert not carpeta_vieja.exists()


def test_renombrar_carpeta_imagenes_unidad_conserva_archivos(conn, tmp_path):
    _configurar_carpeta_base(conn, tmp_path)
    id_unidad = _crear_unidad(conn, unidad="7mo L")
    carpeta_vieja = tmp_path / "Imagenes" / "Unidad_Ramos Mejia_Imperio_7mo L"
    carpeta_vieja.mkdir(parents=True)
    (carpeta_vieja / "foto.jpg").write_text("x")

    conn.execute("UPDATE Unidad SET Departamento = ? WHERE IdUnidad = ?", ("1A", id_unidad))
    conn.commit()
    renombrar_carpeta_imagenes_unidad(conn, id_unidad, "Unidad_Ramos Mejia_Imperio_7mo L")

    carpeta_nueva = tmp_path / "Imagenes" / "Unidad_Ramos Mejia_Imperio_1A"
    assert (carpeta_nueva / "foto.jpg").exists()
    assert not carpeta_vieja.exists()


def test_renombrar_carpeta_imagenes_consultorio_conserva_archivos(conn, tmp_path):
    _configurar_carpeta_base(conn, tmp_path)
    id_consultorio = _crear_consultorio(conn, numero=3)
    carpeta_vieja = tmp_path / "Imagenes" / "Consultorio_Ramos Mejia_Imperio_7mo L_C3"
    carpeta_vieja.mkdir(parents=True)
    (carpeta_vieja / "foto.jpg").write_text("x")

    conn.execute("UPDATE Consultorio SET NumeroConsultorio = 4 WHERE IdConsultorio = ?", (id_consultorio,))
    conn.commit()
    renombrar_carpeta_imagenes_consultorio(conn, id_consultorio, "Consultorio_Ramos Mejia_Imperio_7mo L_C3")

    carpeta_nueva = tmp_path / "Imagenes" / "Consultorio_Ramos Mejia_Imperio_7mo L_C4"
    assert (carpeta_nueva / "foto.jpg").exists()
    assert not carpeta_vieja.exists()


def test_renombrar_carpeta_imagenes_consultorio_sin_cambios_no_hace_nada(conn, tmp_path):
    _configurar_carpeta_base(conn, tmp_path)
    id_consultorio = _crear_consultorio(conn, numero=3)
    carpeta = tmp_path / "Imagenes" / "Consultorio_Ramos Mejia_Imperio_7mo L_C3"
    carpeta.mkdir(parents=True)
    (carpeta / "foto.jpg").write_text("x")

    renombrar_carpeta_imagenes_consultorio(conn, id_consultorio, "Consultorio_Ramos Mejia_Imperio_7mo L_C3")

    assert (carpeta / "foto.jpg").exists()


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
