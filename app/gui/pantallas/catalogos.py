"""Pantallas de catálogo (Localidades, Edificios, Unidades, Consultorios,
Responsables, Tipos de licencia, Listas editables, Condiciones y normas,
Profesiones, Gastos operativos, Placas, Fechas especiales) — todas
construidas sobre PantallaCRUD, sin código bespoke por tabla.
("Mensajes predefinidos" vive aparte, en mensajes_predefinidos.py — tiene
filtro y vista previa propios, sección 5.5. El esquema de descuentos NO
tiene pantalla de catálogo propia — se maneja y se visualiza únicamente
desde la solapa "Esquema de descuentos" de Aumentos y descuentos, ver
app/gui/pantallas/aumentos.py.)"""
from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import QFrame, QLabel, QLineEdit, QMessageBox, QVBoxLayout, QWidget

from app.gui.crud_generico import Campo, PantallaCRUD, campos_libres
from app.gui.widgets.foco import instalar_enter_avanza_foco
from app.gui.widgets.procesando import Procesando
from app.negocio.archivos_generados import (
    nombre_carpeta_consultorio,
    nombre_carpeta_edificio,
    nombre_carpeta_localidad,
    nombre_carpeta_unidad,
    renombrar_carpeta_imagenes_consultorio,
    renombrar_carpeta_imagenes_edificio,
    renombrar_carpeta_imagenes_localidad,
    renombrar_carpeta_imagenes_unidad,
)
from app.negocio.dias import periodo_actual
from app.negocio.feriados import TIPOS_QUE_DESCUENTAN_100
from app.negocio.formato import formatear_moneda
from app.negocio.aumentos import cantidad_liquidaciones_a_regenerar
from app.negocio.gastos_operativos import ALCANCES_GASTO, gasto_en_conflicto, sanear_alcance
from app.negocio.condiciones_normas import reordenar_al_guardar as reordenar_condiciones_al_guardar
from app.negocio.detalles_complementarios import reordenar_al_guardar as reordenar_detalles_al_guardar
from app.negocio.liquidaciones import regenerar_si_corresponde
from app.negocio.listas_editables import opciones_lista, reordenar_al_guardar
from app.negocio.oferta_busqueda import TAMANOS_CONSULTORIO
from app.pdf.estilos import clave_orden_unidad
from app.negocio.validaciones import (
    FORMATO_DIA_MES,
    FORMATO_EMAIL,
    FORMATO_PERIODO,
    es_dia_mes_valido,
    es_email_valido,
    es_periodo_valido,
)
from app.repositorio.registro import obtener_repositorio


def _titulo_campo(texto: str) -> QLabel:
    etiqueta = QLabel(texto)
    etiqueta.setObjectName("subtituloCampo")
    return etiqueta


def _linea_divisoria() -> QFrame:
    linea = QFrame()
    linea.setFrameShape(QFrame.Shape.HLine)
    linea.setFrameShadow(QFrame.Shadow.Sunken)
    return linea


def _opciones_tamano(conn: sqlite3.Connection) -> list[tuple[str | None, str]]:
    return [(None, "Sin clasificar")] + [(t, t) for t in TAMANOS_CONSULTORIO]


def _opciones_localidad(conn: sqlite3.Connection) -> list[tuple[int | None, str]]:
    filas = conn.execute("SELECT IdLocalidad, Localidad FROM Localidad ORDER BY Localidad").fetchall()
    return [(None, "Sin localidad")] + [(f["IdLocalidad"], f["Localidad"]) for f in filas]


def _opciones_edificio(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    filas = conn.execute("SELECT IdEdificio, Nombre FROM Edificio ORDER BY Nombre").fetchall()
    return [(f["IdEdificio"], f["Nombre"]) for f in filas]


def _opciones_unidad(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    # Orden por edificio (alfabético, ya lo hace SQL) y, dentro de cada
    # uno, por piso (PB, EP, después ascendente numérico —
    # `clave_orden_unidad`, pedido explícito de la clienta sobre "todos
    # los selectores similares del sistema", no expresable en el ORDER
    # BY de SQL).
    filas = conn.execute(
        "SELECT u.IdUnidad, u.Departamento, e.Nombre AS Edificio FROM Unidad u "
        "JOIN Edificio e ON e.IdEdificio = u.IdEdificio"
    ).fetchall()
    filas = sorted(filas, key=lambda f: (f["Edificio"], clave_orden_unidad(f["Departamento"])))
    return [(f["IdUnidad"], f"{f['Edificio']} — {f['Departamento']}") for f in filas]


def _opciones_consultorio(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    filas = conn.execute(
        "SELECT c.IdConsultorio, c.NumeroConsultorio, u.Departamento, e.Nombre AS Edificio "
        "FROM Consultorio c JOIN Unidad u ON u.IdUnidad = c.IdUnidad "
        "JOIN Edificio e ON e.IdEdificio = u.IdEdificio"
    ).fetchall()
    filas = sorted(filas, key=lambda f: (f["Edificio"], clave_orden_unidad(f["Departamento"]), f["NumeroConsultorio"]))
    return [
        (f["IdConsultorio"], f"{f['Edificio']} — {f['Departamento']} — Consultorio {f['NumeroConsultorio']}")
        for f in filas
    ]


def _al_actualizar_localidad(conn: sqlite3.Connection, registro_anterior, valores_nuevos: dict) -> None:
    """Al cambiar el nombre de una Localidad, la carpeta de sus
    imágenes se renombra sola para seguir el nombre descriptivo (pedido
    explícito de la clienta: "la idea es que se replique el formato de
    ruta [de Consultorio] para otros elementos", ver `nombre_carpeta_
    localidad`) — `registro_anterior` ya trae el nombre de ANTES de
    guardar directo (no hace falta ningún JOIN, a diferencia de
    Edificio/Unidad/Consultorio, que dependen de un nivel de arriba)."""
    nombre_anterior = nombre_carpeta_localidad(registro_anterior["Localidad"])
    renombrar_carpeta_imagenes_localidad(conn, registro_anterior["IdLocalidad"], nombre_anterior)


def pantalla_localidades(conn: sqlite3.Connection, *, anidado: bool = False) -> PantallaCRUD:
    campos = [
        Campo("Localidad", "Localidad", requerido=True),
        Campo("Partido", "Partido"),
        Campo("Provincia", "Provincia"),
        Campo("Pais", "País"),
        *campos_libres(conn),
    ]
    al_actualizar = lambda registro, valores: _al_actualizar_localidad(conn, registro, valores)  # noqa: E731
    pantalla = PantallaCRUD(
        conn, "Localidad", "Localidades", campos, anidado=anidado, al_actualizar=al_actualizar,
    )
    # al_actualizar queda como weakref dentro de PantallaCRUD (mismo motivo
    # que Fechas especiales, más abajo): hay que anclar la lambda a mano
    # para que no la recolecte el GC apenas retorna esta función.
    pantalla._hook_renombrar_carpeta = al_actualizar
    return pantalla


def _nombre_carpeta_edificio_de_registro(conn: sqlite3.Connection, registro) -> str | None:
    fila_localidad = (
        conn.execute(
            "SELECT Localidad FROM Localidad WHERE IdLocalidad = ?", (registro["IdLocalidad"],),
        ).fetchone()
        if registro["IdLocalidad"] is not None else None
    )
    localidad = fila_localidad["Localidad"] if fila_localidad is not None else None
    return nombre_carpeta_edificio(localidad, registro["Nombre"])


def _al_actualizar_edificio(conn: sqlite3.Connection, registro_anterior, valores_nuevos: dict) -> None:
    """Al cambiar el nombre o la Localidad de un Edificio, la carpeta de
    sus imágenes se renombra sola para seguir el nombre descriptivo
    (mismo criterio que `_al_actualizar_localidad`) — `registro_
    anterior` da los datos de ANTES de guardar; el nombre después se
    recalcula solo, ya con los datos nuevos ya escritos en la base
    (`renombrar_carpeta_imagenes_edificio`)."""
    nombre_anterior = _nombre_carpeta_edificio_de_registro(conn, registro_anterior)
    renombrar_carpeta_imagenes_edificio(conn, registro_anterior["IdEdificio"], nombre_anterior)


def pantalla_edificios(conn: sqlite3.Connection, *, anidado: bool = False) -> PantallaCRUD:
    campos = [
        Campo("Nombre", "Nombre", requerido=True),
        Campo("Domicilio", "Domicilio"),
        Campo("IdLocalidad", "Localidad", tipo="combo", opciones=_opciones_localidad),
        *campos_libres(conn),
    ]
    al_actualizar = lambda registro, valores: _al_actualizar_edificio(conn, registro, valores)  # noqa: E731
    pantalla = PantallaCRUD(
        conn, "Edificio", "Edificios", campos, anidado=anidado, al_actualizar=al_actualizar,
    )
    pantalla._hook_renombrar_carpeta = al_actualizar  # ver comentario análogo en pantalla_localidades
    return pantalla


def _nombre_carpeta_unidad_de_registro(conn: sqlite3.Connection, registro) -> str | None:
    fila_edificio = conn.execute(
        "SELECT e.Nombre AS Edificio, l.Localidad FROM Edificio e "
        "LEFT JOIN Localidad l ON l.IdLocalidad = e.IdLocalidad WHERE e.IdEdificio = ?",
        (registro["IdEdificio"],),
    ).fetchone()
    if fila_edificio is None:
        return None
    return nombre_carpeta_unidad(fila_edificio["Localidad"], fila_edificio["Edificio"], registro["Departamento"])


def _al_actualizar_unidad(conn: sqlite3.Connection, registro_anterior, valores_nuevos: dict) -> None:
    """Al cambiar el Departamento o el Edificio de una Unidad, la
    carpeta de sus imágenes se renombra sola para seguir el nombre
    descriptivo (mismo criterio que `_al_actualizar_localidad`) —
    `registro_anterior` da los datos de ANTES de guardar; el nombre
    después se recalcula solo, ya con los datos nuevos ya escritos en
    la base (`renombrar_carpeta_imagenes_unidad`)."""
    nombre_anterior = _nombre_carpeta_unidad_de_registro(conn, registro_anterior)
    if nombre_anterior is not None:
        renombrar_carpeta_imagenes_unidad(conn, registro_anterior["IdUnidad"], nombre_anterior)


def pantalla_unidades(conn: sqlite3.Connection, *, anidado: bool = False) -> PantallaCRUD:
    campos = [
        Campo("IdEdificio", "Edificio", tipo="combo", opciones=_opciones_edificio, requerido=True),
        Campo("Departamento", "Departamento", requerido=True),
        Campo("Cocina", "Cocina", tipo="booleano"),
        Campo("SalaDeEspera", "Sala de espera", tipo="booleano"),
        # Cantidad, no Sí/No: una unidad puede tener más de un baño
        # (pedido puntual de la clienta al revisar este catálogo).
        Campo("Banos", "Cantidad de baños", tipo="numero"),
        Campo("AreaGuardado", "Área de guardado", tipo="booleano"),
        Campo("AreaDescanso", "Área de descanso", tipo="booleano"),
        Campo("AreaFumadores", "Área de fumadores", tipo="booleano"),
        Campo("Recepcionista", "Recepcionista", tipo="booleano"),
        Campo("BalconComun", "Balcón común", tipo="booleano"),
        Campo("EntradaProfesionalExclusiva", "Entrada exclusiva", tipo="booleano"),
        Campo("WiFi", "WiFi", tipo="booleano"),
        Campo("CantLimitePlacas", "Límite de placas", tipo="numero"),
        *campos_libres(conn),
    ]
    al_actualizar = lambda registro, valores: _al_actualizar_unidad(conn, registro, valores)  # noqa: E731
    pantalla = PantallaCRUD(
        conn, "Unidad", "Unidades", campos, anidado=anidado, al_actualizar=al_actualizar,
    )
    pantalla._hook_renombrar_carpeta = al_actualizar  # ver comentario análogo en pantalla_localidades
    return pantalla


def _nombre_carpeta_consultorio_de_registro(conn: sqlite3.Connection, registro) -> str | None:
    fila_unidad = conn.execute(
        "SELECT u.Departamento, e.Nombre AS Edificio, l.Localidad FROM Unidad u "
        "JOIN Edificio e ON e.IdEdificio = u.IdEdificio "
        "LEFT JOIN Localidad l ON l.IdLocalidad = e.IdLocalidad WHERE u.IdUnidad = ?",
        (registro["IdUnidad"],),
    ).fetchone()
    if fila_unidad is None:
        return None
    return nombre_carpeta_consultorio(
        fila_unidad["Localidad"], fila_unidad["Edificio"], fila_unidad["Departamento"], registro["NumeroConsultorio"],
    )


def _al_actualizar_consultorio(conn: sqlite3.Connection, registro_anterior, valores_nuevos: dict) -> None:
    """Al cambiar la Unidad o el Número de un consultorio, la carpeta de
    sus imágenes se renombra sola para seguir el nombre descriptivo
    (pedido explícito de la clienta, ver `nombre_carpeta_consultorio`) —
    `registro_anterior` da el nombre ANTES de guardar; el nombre después
    se recalcula solo, ya con los datos nuevos ya escritos en la base
    (`renombrar_carpeta_imagenes_consultorio`)."""
    nombre_anterior = _nombre_carpeta_consultorio_de_registro(conn, registro_anterior)
    if nombre_anterior is not None:
        renombrar_carpeta_imagenes_consultorio(conn, registro_anterior["IdConsultorio"], nombre_anterior)


def pantalla_consultorios(conn: sqlite3.Connection, *, anidado: bool = False) -> PantallaCRUD:
    campos = [
        Campo("IdUnidad", "Unidad", tipo="combo", opciones=_opciones_unidad, requerido=True),
        Campo("NumeroConsultorio", "Número", tipo="numero", requerido=True),
        Campo("Largo", "Largo (m)", tipo="numero"),
        Campo("Ancho", "Ancho (m)", tipo="numero"),
        # Tamaño del escritorio (mueble), distinto del Largo/Ancho de
        # arriba (que son del ambiente) — pedido puntual de la clienta,
        # puramente informativo por ahora.
        Campo("LargoEscritorio", "Largo escritorio (m)", tipo="numero"),
        Campo("AnchoEscritorio", "Ancho escritorio (m)", tipo="numero"),
        Campo("TamanoClasificacion", "Clasificación", tipo="combo", opciones=_opciones_tamano),
        Campo("Ventana", "Ventana", tipo="booleano"),
        Campo("Placard", "Placard", tipo="booleano"),
        Campo("AireAcondicionado", "Aire acondicionado", tipo="booleano"),
        Campo("VentiladorTecho", "Ventilador de techo", tipo="booleano"),
        Campo("Sillones", "Sillones", tipo="booleano"),
        Campo("AptoCamilla", "Apto camilla", tipo="booleano"),
        Campo("Balcon", "Balcón", tipo="booleano"),
        Campo("ValorHoraRegularActual", "Valor hora regular actual", tipo="numero", es_monto=True),
        Campo("ValorHoraRegularAnterior", "Valor hora regular anterior", tipo="numero", es_monto=True),
        Campo("ValorHoraAisladaActual", "Valor hora aislada actual", tipo="numero", es_monto=True),
        Campo("ValorHoraAisladaAnterior", "Valor hora aislada anterior", tipo="numero", es_monto=True),
        *campos_libres(conn),
    ]
    al_actualizar = lambda registro, valores: _al_actualizar_consultorio(conn, registro, valores)  # noqa: E731
    pantalla = PantallaCRUD(
        conn, "Consultorio", "Consultorios", campos, anidado=anidado, al_actualizar=al_actualizar,
    )
    # al_actualizar queda como weakref dentro de PantallaCRUD (mismo motivo
    # que Fechas especiales, más abajo): hay que anclar la lambda a mano
    # para que no la recolecte el GC apenas retorna esta función.
    pantalla._hook_renombrar_carpeta = al_actualizar
    return pantalla


def pantalla_responsables(conn: sqlite3.Connection, *, anidado: bool = False) -> PantallaCRUD:
    campos = [
        Campo("Nombre", "Nombre", requerido=True),
        Campo("Celular", "Celular"),
        Campo("Email", "Email", validador=es_email_valido, formato_esperado=FORMATO_EMAIL),
        Campo("Rol", "Rol", tipo="combo", opciones=opciones_lista("RolResponsable"), combo_editable=True),
        Campo("EsContactoPrincipal", "Contacto principal", tipo="booleano"),
        Campo("AptoPDF", "Apto para figurar en PDF", tipo="booleano"),
        Campo("Activo", "Activo", tipo="booleano"),
        *campos_libres(conn),
    ]
    return PantallaCRUD(conn, "Responsable", "Responsables", campos, anidado=anidado)


def pantalla_tipos_licencia(conn: sqlite3.Connection, *, anidado: bool = False) -> PantallaCRUD:
    campos = [
        Campo("Nombre", "Nombre", requerido=True),
        Campo("PorcentajeBonificacion", "% Bonificación", tipo="numero"),
        Campo("DuracionMaximaDias", "Duración máxima (días)", tipo="numero"),
        Campo("EsManual", "Carga manual", tipo="booleano"),
        Campo("Activo", "Activo", tipo="booleano"),
        *campos_libres(conn),
    ]
    return PantallaCRUD(conn, "TipoLicencia", "Tipos de licencia", campos, anidado=anidado)


def _opciones_tipo_lista(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """Solo los tipos que ya existen — esta pantalla es para sumar
    valores a una lista ya usada por otro formulario (CondicionFiscal,
    MedioPago, etc.), no para inventar un tipo nuevo que ningún combo del
    sistema vaya a leer (pedido de la clienta al revisar este catálogo)."""
    filas = conn.execute("SELECT DISTINCT TipoLista FROM ListasEditables ORDER BY TipoLista").fetchall()
    return [(f["TipoLista"], f["TipoLista"]) for f in filas]


def pantalla_listas_editables(conn: sqlite3.Connection, *, anidado: bool = False) -> PantallaCRUD:
    # Campos libres a ancho fijo (igual que "Orden"/"Activo"): pedido
    # explícito de la clienta sobre ESTE catálogo, "Tipo de lista" se
    # lleva TODO el ancho sobrante que no se lleva "Valor" — si los
    # campos libres participaran del reparto (son `Campo` genéricos, no
    # pensados para esto), le estarían sacando parte de ese sobrante.
    campos_libres_ancho_fijo = campos_libres(conn)
    for campo in campos_libres_ancho_fijo:
        campo.ancho_fijo = True
    campos = [
        Campo("TipoLista", "Tipo de lista", tipo="combo", opciones=_opciones_tipo_lista, requerido=True),
        Campo("Valor", "Valor", requerido=True),
        # "Orden"/"Activo" centrados y a ancho fijo (pedido explícito de
        # la clienta): "Valor" se lleva la mitad del ancho sobrante de
        # la tabla, "Tipo de lista" (la única columna que no es ni
        # prioritaria ni de ancho fijo) se lleva la otra mitad — ver
        # `PantallaCRUD.columna_prioritaria`.
        Campo("Orden", "Orden", tipo="numero", centrado=True, ancho_fijo=True),
        Campo("Activo", "Activo", tipo="booleano", centrado=True, ancho_fijo=True),
        *campos_libres_ancho_fijo,
    ]
    pantalla = PantallaCRUD(
        conn, "ListasEditables", "Listas editables", campos, anidado=anidado, columna_prioritaria="Valor",
    )
    pantalla.al_guardar = lambda valores, registro: reordenar_al_guardar(conn, valores, registro)
    return pantalla


def pantalla_condiciones_normas(conn: sqlite3.Connection, *, anidado: bool = False) -> PantallaCRUD:
    campos = [
        Campo("Numero", "N°", requerido=True),
        Campo("Titulo", "Título", requerido=True),
        Campo("Texto", "Texto", tipo="texto_largo", requerido=True),
        Campo("Activo", "Activo", tipo="booleano"),
        *campos_libres(conn),
    ]
    pantalla = PantallaCRUD(conn, "CondicionNorma", "Condiciones y normas", campos, anidado=anidado)
    pantalla.al_guardar = lambda valores, registro: reordenar_condiciones_al_guardar(conn, valores, registro)
    return pantalla


def pantalla_detalles_complementarios_propuesta(conn: sqlite3.Connection, *, anidado: bool = False) -> PantallaCRUD:
    campos = [
        Campo("Orden", "Orden", tipo="numero", requerido=True),
        Campo("Titulo", "Título", requerido=True),
        Campo("Texto", "Texto", tipo="texto_largo", requerido=True),
        Campo("Activo", "Activo", tipo="booleano"),
        *campos_libres(conn),
    ]
    pantalla = PantallaCRUD(
        conn, "DetalleComplementarioPropuesta", "Detalles complementarios (Propuesta)", campos, anidado=anidado,
    )
    pantalla.al_guardar = lambda valores, registro: reordenar_detalles_al_guardar(conn, valores, registro)
    return pantalla


def pantalla_profesiones(conn: sqlite3.Connection, *, anidado: bool = False) -> PantallaCRUD:
    campos = [
        Campo("Nombre", "Nombre", requerido=True),
        Campo("NombreMasculino", "Nombre (masculino)"),
        Campo("NombreFemenino", "Nombre (femenino)"),
        Campo("NombreNeutro", "Nombre (neutro)"),
        Campo("TratamientoDefaultMasculino", "Tratamiento por defecto (masculino)"),
        Campo("TratamientoDefaultFemenino", "Tratamiento por defecto (femenino)"),
        Campo("TieneMultiplesTratamientos", "Tiene múltiples tratamientos", tipo="booleano"),
        Campo("OpcionesTratamientoMasculino", "Opciones de tratamiento (masculino, separadas por coma)"),
        Campo("OpcionesTratamientoFemenino", "Opciones de tratamiento (femenino, separadas por coma)"),
        # Fecha fija anual (sin año) del "día de la profesión" — ej.
        # "13-10" para el 13 de octubre, todos los años. Alimenta el
        # cuadrito "Cumpleaños y días de profesión" de Panel de control.
        # Opcional: dejarlo vacío simplemente no suma nada a ese cuadrito.
        # Formato DD-MM (pedido explícito de la clienta, antes era al
        # revés) agregado directamente al texto de la etiqueta — no solo
        # al mensaje de error de formato_esperado — para que el operador
        # sepa cómo escribirlo sin tener que fallar la validación primero.
        Campo(
            "DiaProfesion", "Día de la profesión (dd-mm)",
            validador=es_dia_mes_valido, formato_esperado=FORMATO_DIA_MES,
        ),
        *campos_libres(conn),
    ]
    return PantallaCRUD(conn, "Profesion", "Profesiones", campos, anidado=anidado)


def _opciones_edificio_o_ninguno_gasto(conn: sqlite3.Connection) -> list[tuple[int | None, str]]:
    return [(None, "Sin relación a edificio específico")] + _opciones_edificio(conn)


def _opciones_unidad_o_ninguna_gasto(conn: sqlite3.Connection) -> list[tuple[int | None, str]]:
    return [(None, "Sin relación a unidad específica")] + _opciones_unidad(conn)


def _opciones_consultorio_o_ninguno_gasto(conn: sqlite3.Connection) -> list[tuple[int | None, str]]:
    return [(None, "Sin relación a consultorio específico")] + _opciones_consultorio(conn)


def _titulo_subtotal_periodo(periodo: str) -> str:
    """"Subtotal gastos período 09-2026": el período se guarda como
    AAAA-MM (`es_periodo_valido`) pero acá se muestra invertido, MM-AAAA
    (pedido de la clienta) — si el texto tipeado en el filtro todavía no
    tiene ese formato (mientras se está escribiendo), se muestra tal
    cual en vez de romper."""
    partes = periodo.split("-")
    if len(partes) == 2:
        anio, mes = partes
        return f"Subtotal gastos período {mes}-{anio}"
    return f"Subtotal gastos período {periodo}"


def _al_abrir_dialogo_gasto(dialogo) -> None:
    """El Alcance (Espacio general/Edificio/Unidad/Consultorio) define
    cuál de los otros tres combos aplica: los que no corresponden quedan
    deshabilitados y se limpian, para que nunca convivan un Alcance
    "Espacio general" con un Edificio cargado (o análogo) — mismo
    criterio de fondo que `gastos_operativos.sanear_alcance`, que hace la
    misma limpieza del lado de los datos por si el gasto se termina
    cargando por otra vía (ej. una futura importación) que no pase por
    este diálogo."""
    combo_alcance = dialogo._entradas["Alcance"]
    combo_edificio = dialogo._entradas["IdEdificio"]
    combo_unidad = dialogo._entradas["IdUnidad"]
    combo_consultorio = dialogo._entradas["IdConsultorio"]

    def _actualizar(*_args) -> None:
        alcance = combo_alcance.currentData()
        combo_edificio.setEnabled(alcance == "Edificio")
        combo_unidad.setEnabled(alcance == "Unidad")
        combo_consultorio.setEnabled(alcance == "Consultorio")
        if alcance != "Edificio":
            combo_edificio.setCurrentIndex(0)
        if alcance != "Unidad":
            combo_unidad.setCurrentIndex(0)
        if alcance != "Consultorio":
            combo_consultorio.setCurrentIndex(0)

    combo_alcance.currentIndexChanged.connect(_actualizar)
    _actualizar()


def pantalla_gastos_operativos(conn: sqlite3.Connection, *, anidado: bool = False) -> PantallaCRUD:
    def opciones_alcance(c):
        return [(a, a) for a in ALCANCES_GASTO]

    def opciones_origen(c):
        return [("Manual", "Manual"), ("Importado", "Importado")]

    campos = [
        Campo(
            "Periodo", "Período (AAAA-MM)", requerido=True,
            validador=es_periodo_valido, formato_esperado=FORMATO_PERIODO,
        ),
        Campo("Categoria", "Categoría", tipo="combo", opciones=opciones_lista("CategoriaGasto"), combo_editable=True),
        Campo("Concepto", "Concepto"),
        Campo("Monto", "Monto", tipo="numero", requerido=True, es_monto=True),
        Campo("Alcance", "Alcance", tipo="combo", opciones=opciones_alcance),
        Campo("IdEdificio", "Edificio", tipo="combo", opciones=_opciones_edificio_o_ninguno_gasto),
        Campo("IdUnidad", "Unidad", tipo="combo", opciones=_opciones_unidad_o_ninguna_gasto),
        Campo("IdConsultorio", "Consultorio", tipo="combo", opciones=_opciones_consultorio_o_ninguno_gasto),
        Campo("Origen", "Origen", tipo="combo", opciones=opciones_origen),
        Campo("Observacion", "Observación", tipo="texto_largo"),
        *campos_libres(conn),
    ]

    panel_periodo = QWidget()
    layout_periodo = QVBoxLayout(panel_periodo)
    layout_periodo.setContentsMargins(0, 0, 0, 0)
    layout_periodo.addWidget(_titulo_campo("Período actual"))
    campo_periodo_filtro = QLineEdit()
    campo_periodo_filtro.setText(periodo_actual(conn))
    layout_periodo.addWidget(campo_periodo_filtro)

    panel_subtotal = QWidget()
    layout_subtotal = QVBoxLayout(panel_subtotal)
    layout_subtotal.setContentsMargins(0, 0, 0, 0)
    layout_subtotal.addWidget(_linea_divisoria())
    etiqueta_titulo_subtotal = _titulo_campo("")
    layout_subtotal.addWidget(etiqueta_titulo_subtotal)
    etiqueta_subtotal = QLabel()
    layout_subtotal.addWidget(etiqueta_subtotal)
    layout_subtotal.addStretch()

    pantalla = PantallaCRUD(
        conn, "GastoOperativo", "Gastos operativos", campos, al_abrir_dialogo=_al_abrir_dialogo_gasto,
        panel_extra_superior_izquierda=panel_periodo, panel_extra_izquierda=panel_subtotal,
        instalar_foco=False, anidado=anidado,
    )
    pantalla.al_guardar = lambda valores, registro: _resolver_conflicto_gasto(pantalla, conn, valores, registro)
    # instalar_foco=False acá arriba: esta pantalla arma su propia cadena
    # de Enter/Tab-avanza-foco (igual criterio que Llaves) para meter
    # "Período actual" entre Buscar y Nuevo, en vez de que PantallaCRUD
    # instale la suya de siempre (que no conoce ese campo extra) — dos
    # filtros de evento distintos sobre los mismos botones no puede ser.
    pantalla._foco = instalar_enter_avanza_foco(
        [pantalla.campo_buscar, campo_periodo_filtro, pantalla.boton_nuevo, pantalla.boton_editar, pantalla.boton_eliminar],
        parent=pantalla,
    )

    def _aplicar_filtro_periodo() -> None:
        periodo = campo_periodo_filtro.text().strip() or periodo_actual(conn)
        tabla = pantalla.tabla_widget
        for fila in range(tabla.rowCount()):
            item_periodo = tabla.item(fila, 0)
            texto = item_periodo.text() if item_periodo else ""
            tabla.setRowHidden(fila, texto != periodo)
        gastos_del_periodo = obtener_repositorio(conn, "GastoOperativo").listar(Periodo=periodo)
        subtotal = sum(g["Monto"] or 0 for g in gastos_del_periodo)
        etiqueta_titulo_subtotal.setText(_titulo_subtotal_periodo(periodo))
        etiqueta_subtotal.setText(formatear_moneda(subtotal))

    campo_periodo_filtro.editingFinished.connect(_aplicar_filtro_periodo)
    actualizar_original = pantalla.actualizar

    def _actualizar_con_periodo() -> None:
        actualizar_original()
        _aplicar_filtro_periodo()

    pantalla.actualizar = _actualizar_con_periodo
    pantalla.actualizar()
    return pantalla


def _resolver_conflicto_gasto(parent, conn: sqlite3.Connection, valores: dict, registro) -> dict | None:
    valores = sanear_alcance(valores)
    id_actual = registro["IdGasto"] if registro is not None else None
    conflicto = gasto_en_conflicto(
        conn, periodo=valores.get("Periodo"), concepto=valores.get("Concepto"),
        origen=valores.get("Origen"), id_gasto_actual=id_actual,
    )
    if conflicto is None:
        return valores
    respuesta = QMessageBox.question(
        parent, "Conflicto de origen",
        f"Ya existe un gasto operativo \"{conflicto['Concepto']}\" del período {conflicto['Periodo']} con "
        f"origen \"{conflicto['Origen']}\" ({formatear_moneda(conflicto['Monto'])}). No pueden convivir un origen Manual "
        f"y uno Importado para el mismo concepto y período.\n\n¿Reemplazarlo por este nuevo valor "
        f"(\"{valores.get('Origen')}\")?",
    )
    if respuesta != QMessageBox.StandardButton.Yes:
        return None
    obtener_repositorio(conn, "GastoOperativo").eliminar(conflicto["IdGasto"])
    return valores


def _afecta_periodo_actual(conn: sqlite3.Connection, fecha: str | None) -> bool:
    return bool(fecha) and fecha[:7] == periodo_actual(conn)


def _regenerar_liquidaciones_del_periodo_actual(conn: sqlite3.Connection) -> None:
    periodo = periodo_actual(conn)
    ids_profesional = {f["IdProfesional"] for f in obtener_repositorio(conn, "LiquidacionEmitida").listar(Periodo=periodo)}
    with Procesando(None, "Regenerando liquidaciones...") as procesando:
        for id_profesional in ids_profesional:
            regenerar_si_corresponde(conn, id_profesional=id_profesional, periodo=periodo)
            procesando.tick()
    # Pedido explícito de la clienta: que SIEMPRE quede claro que esto
    # regeneró archivos y los marcó como no enviados, con un "proceso
    # completado" al terminar — mismo criterio que ya usan Aumentos y
    # Esquema de descuentos (cartel de éxito con la cantidad real
    # regenerada, después de que ya se hizo). Antes de esto no había
    # ningún cartel para el caso de Eliminar (no se puede avisar ANTES,
    # ver `_al_eliminar_fecha_especial`), así que esta es la única
    # confirmación visible de que el proceso terminó.
    if ids_profesional:
        QMessageBox.information(
            None, "Fechas especiales",
            f"Se regeneraron {len(ids_profesional)} liquidación(es) ya emitida(s) del período {periodo}: "
            "quedaron marcadas como no enviadas.",
        )


def _al_guardar_fecha_especial(valores: dict, registro, conn: sqlite3.Connection) -> dict | None:
    """Pedido explícito de la clienta: crear/editar un feriado o fecha
    especial del período en curso dispara el mismo aviso de
    regeneración que ya tiene Aumentos ("Hay N liquidación(es) ya
    emitida(s)... ¿Confirmás?") — antes de guardar, no solo después.
    Mira tanto la fecha nueva como la que tenía antes de editar (si se
    la corre fuera del período en curso, también hay que avisar)."""
    fecha_nueva = valores.get("Fecha")
    fecha_vieja = registro["Fecha"] if registro is not None else None
    if not (_afecta_periodo_actual(conn, fecha_nueva) or _afecta_periodo_actual(conn, fecha_vieja)):
        return valores
    cantidad = cantidad_liquidaciones_a_regenerar(conn, periodo_actual(conn))
    if cantidad == 0:
        return valores
    respuesta = QMessageBox.question(
        None, "Fechas especiales",
        f"Hay {cantidad} liquidación(es) ya emitida(s) para el período en curso ({periodo_actual(conn)}): "
        "este cambio las va a regenerar y van a quedar marcadas como no enviadas. ¿Confirmás?",
    )
    return valores if respuesta == QMessageBox.StandardButton.Yes else None


def _al_crear_fecha_especial(conn: sqlite3.Connection, _id_nuevo: int, valores: dict) -> None:
    if _afecta_periodo_actual(conn, valores.get("Fecha")):
        _regenerar_liquidaciones_del_periodo_actual(conn)


def _al_actualizar_fecha_especial(conn: sqlite3.Connection, registro, valores: dict) -> None:
    if _afecta_periodo_actual(conn, valores.get("Fecha")) or _afecta_periodo_actual(conn, registro["Fecha"]):
        _regenerar_liquidaciones_del_periodo_actual(conn)


def _al_eliminar_fecha_especial(conn: sqlite3.Connection, registro) -> None:
    """A diferencia de crear/editar, acá no hay forma de preguntar ANTES
    de eliminar (`al_eliminar` corre después del borrado — el cartel
    genérico de "¿Confirmás eliminar?" de `PantallaCRUD` ya sirvió de
    confirmación para la acción en sí): se regenera directo, sin pedir
    una segunda confirmación."""
    if _afecta_periodo_actual(conn, registro["Fecha"]):
        _regenerar_liquidaciones_del_periodo_actual(conn)


def _antes_de_eliminar_fecha_especial(conn: sqlite3.Connection, registro) -> str | None:
    """Pedido explícito de la clienta ("anular un feriado" — caso
    hipotético e improbable, pero delicado): a diferencia de `al_
    eliminar` (corre DESPUÉS del borrado, solo para reaccionar), esto
    usa el hook `antes_de_eliminar` de `PantallaCRUD` para BLOQUEAR la
    eliminación cuando haga falta — sin forma automática segura de
    resolverlo, el sistema obliga a revisar caso por caso: hay que
    cancelar a mano, una por una, las reservas aisladas confirmadas ese
    día (probablemente cargadas asumiendo que el día estaba libre por
    ser feriado — ver `verificar_conflictos_aislada`, que deja de
    chequear la reserva regular en un día feriado) antes de poder
    anular el feriado en sí."""
    if registro["Tipo"] not in TIPOS_QUE_DESCUENTAN_100:
        return None
    aisladas = obtener_repositorio(conn, "ReservaAislada").listar(Fecha=registro["Fecha"], Estado="Confirmada")
    if not aisladas:
        return None
    return (
        f"No se puede eliminar: hay {len(aisladas)} reserva(s) aislada(s) confirmada(s) el "
        f"{registro['Fecha']}, probablemente cargada(s) asumiendo que ese día era feriado. "
        "Cancelá esas reservas una por una antes de anular el feriado."
    )


def pantalla_fechas_especiales(conn: sqlite3.Connection, *, anidado: bool = False) -> PantallaCRUD:
    campos = [
        # requerido=True: la columna es NOT NULL en el schema — sin esto,
        # "Nuevo" sin tocar el campo deja la fecha en el sentinel "(sin
        # fecha)" (ver `_FECHA_SIN_DATO`) y el guardado revienta con un
        # IntegrityError (bug real, encontrado al revisar esta pantalla).
        Campo("Fecha", "Fecha", tipo="fecha", requerido=True),
        Campo("Descripcion", "Descripción"),
        Campo("Tipo", "Tipo", tipo="combo", opciones=opciones_lista("TipoFechaEspecial")),
        Campo("Activo", "Activo", tipo="booleano"),
        *campos_libres(conn),
    ]
    al_crear = lambda id_nuevo, valores: _al_crear_fecha_especial(conn, id_nuevo, valores)  # noqa: E731
    al_actualizar = lambda registro, valores: _al_actualizar_fecha_especial(conn, registro, valores)  # noqa: E731
    al_eliminar = lambda registro: _al_eliminar_fecha_especial(conn, registro)  # noqa: E731
    antes_de_eliminar = lambda registro: _antes_de_eliminar_fecha_especial(conn, registro)  # noqa: E731
    pantalla = PantallaCRUD(
        conn, "FechasEspeciales", "Fechas especiales", campos, anidado=anidado,
        al_guardar=lambda valores, registro: _al_guardar_fecha_especial(valores, registro, conn),
        al_crear=al_crear, al_actualizar=al_actualizar, al_eliminar=al_eliminar,
        antes_de_eliminar=antes_de_eliminar,
    )
    # `al_crear`/`al_actualizar`/`al_eliminar`/`antes_de_eliminar` quedan
    # como weakref dentro de `PantallaCRUD` (mismo motivo que Llaves:
    # evitar un ciclo pantalla -> PantallaCRUD -> pantalla) — acá son
    # lambdas sueltas, sin ninguna pantalla compuesta que las sostenga,
    # así que hay que anclarlas a mano para que no las recolecte el GC
    # apenas retorna esta función.
    pantalla._hooks_regeneracion = (al_crear, al_actualizar, al_eliminar, antes_de_eliminar)
    return pantalla
