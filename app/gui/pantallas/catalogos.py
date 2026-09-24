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
from app.negocio.dias import periodo_actual
from app.negocio.formato import formatear_moneda
from app.negocio.gastos_operativos import ALCANCES_GASTO, gasto_en_conflicto, sanear_alcance
from app.negocio.condiciones_normas import reordenar_al_guardar as reordenar_condiciones_al_guardar
from app.negocio.detalles_complementarios import reordenar_al_guardar as reordenar_detalles_al_guardar
from app.negocio.listas_editables import opciones_lista, reordenar_al_guardar
from app.negocio.oferta_busqueda import TAMANOS_CONSULTORIO
from app.negocio.validaciones import (
    FORMATO_EMAIL,
    FORMATO_PERIODO,
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
    filas = conn.execute(
        "SELECT u.IdUnidad, u.Departamento, e.Nombre AS Edificio FROM Unidad u "
        "JOIN Edificio e ON e.IdEdificio = u.IdEdificio ORDER BY e.Nombre, u.Departamento"
    ).fetchall()
    return [(f["IdUnidad"], f"{f['Edificio']} — {f['Departamento']}") for f in filas]


def _opciones_consultorio(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    filas = conn.execute(
        "SELECT c.IdConsultorio, c.NumeroConsultorio, u.Departamento, e.Nombre AS Edificio "
        "FROM Consultorio c JOIN Unidad u ON u.IdUnidad = c.IdUnidad "
        "JOIN Edificio e ON e.IdEdificio = u.IdEdificio ORDER BY e.Nombre, u.Departamento, c.NumeroConsultorio"
    ).fetchall()
    return [
        (f["IdConsultorio"], f"{f['Edificio']} — {f['Departamento']} — Consultorio {f['NumeroConsultorio']}")
        for f in filas
    ]


def pantalla_localidades(conn: sqlite3.Connection, *, anidado: bool = False) -> PantallaCRUD:
    campos = [
        Campo("Localidad", "Localidad", requerido=True),
        Campo("Partido", "Partido"),
        Campo("Provincia", "Provincia"),
        Campo("Pais", "País"),
        *campos_libres(conn),
    ]
    return PantallaCRUD(conn, "Localidad", "Localidades", campos, anidado=anidado)


def pantalla_edificios(conn: sqlite3.Connection, *, anidado: bool = False) -> PantallaCRUD:
    campos = [
        Campo("Nombre", "Nombre", requerido=True),
        Campo("Domicilio", "Domicilio"),
        Campo("IdLocalidad", "Localidad", tipo="combo", opciones=_opciones_localidad),
        *campos_libres(conn),
    ]
    return PantallaCRUD(conn, "Edificio", "Edificios", campos, anidado=anidado)


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
    return PantallaCRUD(conn, "Unidad", "Unidades", campos, anidado=anidado)


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
        Campo("ValorHoraRegularActual", "Valor hora regular actual", tipo="numero"),
        Campo("ValorHoraRegularAnterior", "Valor hora regular anterior", tipo="numero"),
        Campo("ValorHoraAisladaActual", "Valor hora aislada actual", tipo="numero"),
        Campo("ValorHoraAisladaAnterior", "Valor hora aislada anterior", tipo="numero"),
        *campos_libres(conn),
    ]
    return PantallaCRUD(conn, "Consultorio", "Consultorios", campos, anidado=anidado)


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
    campos = [
        Campo("TipoLista", "Tipo de lista", tipo="combo", opciones=_opciones_tipo_lista, requerido=True),
        Campo("Valor", "Valor", requerido=True),
        Campo("Orden", "Orden", tipo="numero"),
        Campo("Activo", "Activo", tipo="booleano"),
    ]
    pantalla = PantallaCRUD(conn, "ListasEditables", "Listas editables", campos, anidado=anidado)
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
        *campos_libres(conn),
    ]
    return PantallaCRUD(conn, "Profesion", "Profesiones", campos, anidado=anidado)


def _opciones_edificio_o_ninguno_gasto(conn: sqlite3.Connection) -> list[tuple[int | None, str]]:
    return [(None, "Sin relación a edificio específico")] + _opciones_edificio(conn)


def _opciones_unidad_o_ninguna_gasto(conn: sqlite3.Connection) -> list[tuple[int | None, str]]:
    return [(None, "Sin relación a unidad específica")] + _opciones_unidad(conn)


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
    """El Alcance (Espacio general/Edificio/Unidad) define cuál de los
    otros dos combos aplica: el que no corresponde queda deshabilitado y
    se limpia, para que nunca convivan un Alcance "Espacio general" con
    un Edificio cargado (o análogo) — mismo criterio de fondo que
    `gastos_operativos.sanear_alcance`, que hace la misma limpieza del
    lado de los datos por si el gasto se termina cargando por otra vía
    (ej. una futura importación) que no pase por este diálogo."""
    combo_alcance = dialogo._entradas["Alcance"]
    combo_edificio = dialogo._entradas["IdEdificio"]
    combo_unidad = dialogo._entradas["IdUnidad"]

    def _actualizar(*_args) -> None:
        alcance = combo_alcance.currentData()
        combo_edificio.setEnabled(alcance == "Edificio")
        combo_unidad.setEnabled(alcance == "Unidad")
        if alcance != "Edificio":
            combo_edificio.setCurrentIndex(0)
        if alcance != "Unidad":
            combo_unidad.setCurrentIndex(0)

    combo_alcance.currentIndexChanged.connect(_actualizar)
    _actualizar()


def pantalla_gastos_operativos(conn: sqlite3.Connection) -> PantallaCRUD:
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
        Campo("Monto", "Monto", tipo="numero", requerido=True),
        Campo("Alcance", "Alcance", tipo="combo", opciones=opciones_alcance),
        Campo("IdEdificio", "Edificio", tipo="combo", opciones=_opciones_edificio_o_ninguno_gasto),
        Campo("IdUnidad", "Unidad", tipo="combo", opciones=_opciones_unidad_o_ninguna_gasto),
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
        instalar_foco=False,
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


def pantalla_placas(conn: sqlite3.Connection, *, anidado: bool = False) -> PantallaCRUD:
    def opciones_profesional(c):
        filas = c.execute("SELECT IdProfesional, Apellido, NombrePila FROM Profesional ORDER BY Apellido").fetchall()
        return [(f["IdProfesional"], f"{f['Apellido']}, {f['NombrePila'] or ''}".strip(", ")) for f in filas]

    campos = [
        Campo("IdUnidad", "Unidad", tipo="combo", opciones=_opciones_unidad, requerido=True),
        Campo("PosicionTablero", "Posición en el tablero", tipo="numero"),
        Campo("IdProfesional", "Profesional", tipo="combo", opciones=opciones_profesional),
        Campo("NombreGrabado", "Nombre grabado"),
        Campo("EsPersonalizada", "Es personalizada", tipo="booleano"),
        Campo("Activo", "Activo", tipo="booleano"),
    ]
    return PantallaCRUD(conn, "Placa", "Placas", campos, anidado=anidado)


def pantalla_fechas_especiales(conn: sqlite3.Connection, *, anidado: bool = False) -> PantallaCRUD:
    campos = [
        Campo("Fecha", "Fecha", tipo="fecha"),
        Campo("Descripcion", "Descripción"),
        Campo("Tipo", "Tipo", tipo="combo", opciones=opciones_lista("TipoFechaEspecial")),
        Campo("Activo", "Activo", tipo="booleano"),
        *campos_libres(conn),
    ]
    return PantallaCRUD(conn, "FechasEspeciales", "Fechas especiales", campos, anidado=anidado)
