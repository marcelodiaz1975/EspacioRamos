import sqlite3

from app.db.init_db import init_database
from app.db.migraciones import aplicar_migraciones


def test_base_nueva_ya_tiene_las_columnas_migradas(tmp_path):
    conn = init_database(tmp_path / "test.db")
    columnas = {f["name"] for f in conn.execute("PRAGMA table_info(Ausencia)").fetchall()}
    assert "IdReservaAislada" in columnas
    assert "HoraInicio" in columnas
    assert "HoraFin" in columnas
    columnas_pagos = {f["name"] for f in conn.execute("PRAGMA table_info(HistorialPagos)").fetchall()}
    assert "SaldoAnterior" in columnas_pagos
    assert "SaldoNuevo" in columnas_pagos
    assert "RegistroModificado" in columnas_pagos
    conn.close()


def test_aplicar_migraciones_agrega_tamano_de_escritorio_a_consultorio_viejo(tmp_path):
    """Simula una base creada antes de que existiera el tamaño del
    escritorio: Consultorio sin esas dos columnas — confirma que
    aplicar_migraciones las agrega solas."""
    conn = sqlite3.connect(tmp_path / "vieja.db")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE Consultorio (IdConsultorio INTEGER PRIMARY KEY, IdUnidad INTEGER NOT NULL, "
        "NumeroConsultorio INTEGER NOT NULL, TamanoClasificacion TEXT)"
    )
    conn.commit()

    aplicar_migraciones(conn)

    columnas = {f["name"] for f in conn.execute("PRAGMA table_info(Consultorio)").fetchall()}
    assert {"LargoEscritorio", "AnchoEscritorio"} <= columnas
    conn.close()


def test_base_nueva_tiene_las_tablas_de_seguridad(tmp_path):
    conn = init_database(tmp_path / "test.db")
    tablas = {
        f["name"] for f in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    }
    assert {"NivelAcceso", "Usuario", "HistorialContrasenas", "PermisoPantalla"} <= tablas
    conn.close()


def test_aplicar_migraciones_agrega_columnas_de_seguridad_a_configuracion_vieja(tmp_path):
    """Simula una base creada antes de la solapa Seguridad: Configuracion
    sin sus tres columnas nuevas — confirma que aplicar_migraciones las
    agrega solas."""
    conn = sqlite3.connect(tmp_path / "vieja.db")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE Configuracion (IdConfiguracion INTEGER PRIMARY KEY CHECK (IdConfiguracion = 1))")
    conn.commit()

    aplicar_migraciones(conn)

    columnas = {f["name"] for f in conn.execute("PRAGMA table_info(Configuracion)").fetchall()}
    assert {"MinutosInactividadBloqueo", "ContrasenaMaestraHash", "ContrasenaMaestraSalt"} <= columnas
    conn.close()


def test_aplicar_migraciones_ignora_tabla_que_no_existe_todavia(tmp_path):
    """Una base vieja de verdad puede no tener ni siquiera alguna de las
    tablas que ganaron columnas nuevas más adelante — no debería romper,
    solo salteársela (nada que migrarle todavía)."""
    conn = sqlite3.connect(tmp_path / "sin_tabla.db")
    conn.row_factory = sqlite3.Row
    aplicar_migraciones(conn)  # no debe lanzar excepción
    conn.close()


def test_aplicar_migraciones_agrega_la_columna_a_una_base_vieja(tmp_path):
    """Simula una base creada antes de que existiera la columna: la crea
    a mano sin ella (como si viniera de un schema.sql viejo) y confirma
    que aplicar_migraciones la agrega sola."""
    db_path = tmp_path / "vieja.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE Ausencia (IdAusencia INTEGER PRIMARY KEY, IdProfesional INTEGER NOT NULL, "
        "IdConsultorio INTEGER, FechaDesde TEXT NOT NULL, FechaHasta TEXT NOT NULL, Motivo TEXT, Observacion TEXT)"
    )
    conn.commit()
    columnas_antes = {f["name"] for f in conn.execute("PRAGMA table_info(Ausencia)").fetchall()}
    assert "IdReservaAislada" not in columnas_antes

    aplicar_migraciones(conn)

    columnas_despues = {f["name"] for f in conn.execute("PRAGMA table_info(Ausencia)").fetchall()}
    assert "IdReservaAislada" in columnas_despues
    conn.close()


def test_aplicar_migraciones_es_idempotente(tmp_path):
    conn = init_database(tmp_path / "test.db")
    aplicar_migraciones(conn)  # segunda vez, no debería fallar ni duplicar la columna
    columnas = [f["name"] for f in conn.execute("PRAGMA table_info(Ausencia)").fetchall()]
    assert columnas.count("IdReservaAislada") == 1
    conn.close()


def test_aplicar_migraciones_borra_historial_oferta_de_una_base_vieja(tmp_path):
    """Decisión de la clienta: no se guarda ningún historial de búsquedas
    de Oferta de consultorios — una base vieja que todavía tenga la
    tabla la pierde al abrirse con esta versión."""
    conn = init_database(tmp_path / "test.db")
    conn.execute(
        "CREATE TABLE HistorialOferta (IdHistorialOferta INTEGER PRIMARY KEY, "
        "IdProfesional INTEGER NOT NULL, FechaGeneracion TEXT NOT NULL, CriteriosJSON TEXT NOT NULL)"
    )
    conn.commit()

    aplicar_migraciones(conn)

    tabla = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'HistorialOferta'"
    ).fetchone()
    assert tabla is None
    conn.close()


def test_aplicar_migraciones_reemplaza_panel_de_vidrio_por_placard(tmp_path):
    """Panel de vidrio/luz natural se saca como característica a cargar
    del consultorio; Placard ocupa su lugar (decisión de la clienta) —
    no es un simple cambio de nombre, así que el valor viejo no se
    traslada a la columna nueva."""
    conn = init_database(tmp_path / "test.db")
    conn.execute("ALTER TABLE Consultorio ADD COLUMN PanelVidrioLuzNatural INTEGER NOT NULL DEFAULT 0")
    conn.commit()

    aplicar_migraciones(conn)

    columnas = {f["name"] for f in conn.execute("PRAGMA table_info(Consultorio)").fetchall()}
    assert "Placard" in columnas
    assert "PanelVidrioLuzNatural" not in columnas
    conn.close()


def test_aplicar_migraciones_normaliza_tamano_de_consultorio(tmp_path):
    """Consultorio.TamanoClasificacion pasó de texto libre a catálogo
    cerrado (Grande/Intermedio/Chico): una base vieja con mayúsculas
    distintas se corrige, y cualquier otro valor viejo se vacía — si no,
    el filtro de tamaño de Oferta de consultorios (que compara por
    igualdad exacta) nunca encontraría coincidencia con esos registros."""
    conn = init_database(tmp_path / "test.db")
    id_edificio = conn.execute("INSERT INTO Edificio (Nombre) VALUES ('Ramos 1')").lastrowid
    id_unidad = conn.execute(
        "INSERT INTO Unidad (IdEdificio, Departamento) VALUES (?, '1A')", (id_edificio,)
    ).lastrowid
    conn.execute(
        "INSERT INTO Consultorio (IdUnidad, NumeroConsultorio, TamanoClasificacion) VALUES (?, 1, 'grande')",
        (id_unidad,),
    )
    conn.execute(
        "INSERT INTO Consultorio (IdUnidad, NumeroConsultorio, TamanoClasificacion) VALUES (?, 2, 'Pequeño')",
        (id_unidad,),
    )
    conn.commit()

    aplicar_migraciones(conn)

    valores = {
        f["NumeroConsultorio"]: f["TamanoClasificacion"]
        for f in conn.execute("SELECT NumeroConsultorio, TamanoClasificacion FROM Consultorio").fetchall()
    }
    assert valores[1] == "Grande"
    assert valores[2] is None
    conn.close()


def test_base_nueva_siembra_supervisor_general_via_seed_no_via_migracion(tmp_path):
    """Una base recién creada (sin `sembrar_valores_por_defecto` todavía)
    no debería recibir "Supervisor general" desde `aplicar_migraciones` —
    eso lo hace `app.db.seed.sembrar_niveles_acceso` más adelante. Si la
    migración insertara la fila acá, `NivelAcceso` dejaría de estar vacía
    y `sembrar_niveles_acceso` (que solo siembra si la tabla está vacía)
    nunca llegaría a cargar Administrador/Operador."""
    conn = init_database(tmp_path / "test.db")
    filas = conn.execute("SELECT Nombre FROM NivelAcceso").fetchall()
    assert filas == []
    conn.close()


def test_aplicar_migraciones_agrega_supervisor_general_a_base_ya_sembrada(tmp_path):
    """Simula una base ya en uso, con Administrador/Operador cargados
    (como si viniera de antes de sumar el tercer nivel) — confirma que
    aplicar_migraciones agrega la fila que falta."""
    conn = sqlite3.connect(tmp_path / "vieja.db")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE NivelAcceso (IdNivelAcceso INTEGER PRIMARY KEY, Nombre TEXT UNIQUE NOT NULL, "
        "Orden INTEGER NOT NULL, Activo INTEGER NOT NULL DEFAULT 1)"
    )
    conn.executemany(
        "INSERT INTO NivelAcceso (Nombre, Orden, Activo) VALUES (?, ?, 1)",
        [("Administrador", 100), ("Operador", 10)],
    )
    conn.commit()

    aplicar_migraciones(conn)

    filas = {f["Nombre"]: f["Orden"] for f in conn.execute("SELECT Nombre, Orden FROM NivelAcceso").fetchall()}
    assert filas == {"Supervisor general": 1000, "Administrador": 100, "Operador": 10}
    conn.close()


def test_aplicar_migraciones_es_idempotente_para_supervisor_general(tmp_path):
    """Correr aplicar_migraciones dos veces sobre la misma base no debería
    duplicar la fila de Supervisor general."""
    conn = sqlite3.connect(tmp_path / "vieja.db")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE NivelAcceso (IdNivelAcceso INTEGER PRIMARY KEY, Nombre TEXT UNIQUE NOT NULL, "
        "Orden INTEGER NOT NULL, Activo INTEGER NOT NULL DEFAULT 1)"
    )
    conn.executemany(
        "INSERT INTO NivelAcceso (Nombre, Orden, Activo) VALUES (?, ?, 1)",
        [("Administrador", 100), ("Operador", 10)],
    )
    conn.commit()

    aplicar_migraciones(conn)
    aplicar_migraciones(conn)

    cantidad = conn.execute(
        "SELECT COUNT(*) AS c FROM NivelAcceso WHERE Nombre = 'Supervisor general'"
    ).fetchone()["c"]
    assert cantidad == 1
    conn.close()


def test_aplicar_migraciones_ignora_nivel_acceso_que_no_existe_todavia(tmp_path):
    """Una base sin la tabla NivelAcceso (de antes de la solapa Seguridad)
    no debería romper — solo salteársela."""
    conn = sqlite3.connect(tmp_path / "sin_seguridad.db")
    conn.row_factory = sqlite3.Row
    aplicar_migraciones(conn)  # no debe lanzar excepción
    conn.close()
