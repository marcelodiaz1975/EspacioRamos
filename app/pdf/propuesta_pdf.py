"""PDF de Propuesta al profesional (Etapa 7, sección 4.3). Para
profesionales NO activos (categoría C/contacto, o cualquiera que todavía
no tenga reservas confirmadas): a diferencia del PDF de Disponibilidad,
anonimiza las unidades como "Unidad {IdUnidad}" en vez de mostrar el
Departamento real, para no revelar información interna del edificio a
alguien que todavía no forma parte del espacio.

Secciones (orden y contenido tomados del modelo real de referencia del
documento): Detalles principales de la propuesta (Ubicación, Destino y
uso del espacio, Detalle de las unidades, Detalle de los consultorios,
por edificio) -> Fotos de los consultorios (con valor de la hora regular
y ✔ Apto camilla, información útil para quien todavía no conoce el
espacio) -> Disponibilidad -> Condiciones y forma de reserva (dinámica,
a partir de BloqueRigido/Configuracion) -> Valores vigentes por hora
regular -> Detalles complementarios de la propuesta (editable, tabla
DetalleComplementarioPropuesta). No incluye "Condiciones y normas"
(CondicionNorma): ese contenido queda reservado al PDF de Liquidación,
donde no se superpone con "Detalles complementarios"."""
from __future__ import annotations

import os
import sqlite3

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from app.negocio.dias import fecha_actual, parsear_periodo, periodo_actual
from app.negocio.formato import fecha_larga
from app.pdf.edificios_pdf import edificios_incluidos, ids_consultorio_de_edificios, sufijo_localidad
from app.pdf.estilos import (
    COLOR_NIVEL_1,
    FUENTE,
    FUENTE_NEGRITA,
    clave_orden_unidad,
    crear_documento,
    decimales_configurados,
    encabezado,
    encabezado_espacio,
    estilo_texto,
)
from app.pdf.fotos_pdf import imagenes_de_consultorios, tabla_fotos
from app.pdf.grilla_pdf import altura_estimada_grilla, secciones_disponibilidad
from app.pdf.valores_pdf import condiciones_forma_reserva, detalles_complementarios_propuesta, matriz_valores_edificio
from app.repositorio.registro import obtener_repositorio

_TEXTO_DESTINO_USO = (
    "El uso de los consultorios se encuentra dirigido a la realización de terapias individuales de salud "
    "mental, nutrición y similares."
)


def _contacto_y_profesion(conn: sqlite3.Connection, profesional: sqlite3.Row | None) -> list:
    cfg = conn.execute("SELECT * FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    style = estilo_texto(9)
    story = []
    if cfg and (cfg["ContactoCelular"] or cfg["ContactoEmail"]):
        contacto = " / ".join(c for c in (cfg["ContactoCelular"], cfg["ContactoEmail"]) if c)
        story.append(Paragraph(f"<b>Contacto:</b> {contacto}", style))
    if profesional is not None:
        profesion = obtener_repositorio(conn, "Profesion").obtener(profesional["IdProfesion"]) if profesional["IdProfesion"] else None
        if profesion:
            story.append(Paragraph(f"<b>Profesión de interés:</b> {profesion['Nombre']}", style))
    if story:
        story.append(Spacer(1, 6))
    return story


def _medida(valor: float | None) -> str:
    return f"{valor:.2f}".replace(".", ",") if valor is not None else "—"


def _si_no(valor) -> str:
    return "Sí" if valor else "No"


def _encabezados_tabla(textos: list[str], tamano: int = 7) -> list[Paragraph]:
    """Encabezados envueltos en Paragraph en vez de texto plano: con tantas
    columnas ("Detalle de las unidades" tiene 10) el texto plano se
    superpone con la columna siguiente en vez de hacer salto de línea
    dentro de la celda."""
    style = estilo_texto(tamano, negrita=True, alignment=TA_CENTER, textColor=colors.white)
    return [Paragraph(t, style) for t in textos]


def _tabla_detalle_unidades(conn: sqlite3.Connection, id_edificio: int, ancho: float) -> list:
    filas_bd = conn.execute(
        """
        SELECT u.IdUnidad, u.Departamento, u.SalaDeEspera, u.Cocina, u.Banos, u.WiFi, u.BalconComun,
               u.EntradaProfesionalExclusiva, u.AreaGuardado, u.AreaFumadores,
               (SELECT COUNT(*) FROM Consultorio c WHERE c.IdUnidad = u.IdUnidad) AS CantConsultorios
        FROM Unidad u WHERE u.IdEdificio = ?
        """,
        (id_edificio,),
    ).fetchall()
    if not filas_bd:
        return [Paragraph("Sin unidades cargadas.", estilo_texto(9))]
    filas_bd = sorted(filas_bd, key=lambda f: clave_orden_unidad(f["Departamento"]))

    encabezados = [
        "Unidad", "Consultorios", "Sala de espera", "Cocina", "Baños", "WiFi",
        "Balcón de uso común", "Entrada profesional exclusiva", "Área de guardado", "Área de fumadores",
    ]
    filas = [_encabezados_tabla(encabezados)]
    for f in filas_bd:
        filas.append([
            f"Unidad {f['IdUnidad']}", str(f["CantConsultorios"]), _si_no(f["SalaDeEspera"]), _si_no(f["Cocina"]),
            _si_no(f["Banos"]), _si_no(f["WiFi"]), _si_no(f["BalconComun"]), _si_no(f["EntradaProfesionalExclusiva"]),
            _si_no(f["AreaGuardado"]), _si_no(f["AreaFumadores"]),
        ])

    # Columnas de nombre corto (Cocina/Baños/WiFi) más angostas que las de
    # nombre largo (Balcón de uso común/Entrada profesional exclusiva):
    # con 10 columnas en total, repartir el ancho parejo hace que el
    # encabezado de las columnas largas necesite 3-4 líneas.
    proporciones = [0.09, 0.11, 0.085, 0.07, 0.075, 0.065, 0.115, 0.135, 0.1125, 0.1125]
    anchos = [ancho * p for p in proporciones]
    tabla = Table(filas, colWidths=anchos, repeatRows=1)
    tabla.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), FUENTE_NEGRITA), ("FONTNAME", (0, 1), (-1, -1), FUENTE),
        ("FONTSIZE", (0, 0), (-1, -1), 7), ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("GRID", (0, 0), (-1, -1), 0.5, "#000000"),
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_NIVEL_1), ("TEXTCOLOR", (0, 0), (-1, 0), "#FFFFFF"),
    ]))
    return [tabla]


def _tabla_consultorios(filas_bd: list[sqlite3.Row], ancho: float) -> Table:
    encabezados = [
        "Consultorio", "Medidas en metros", "Ventana", "Balcón", "Ladrillos de vidrio",
        "Aire acondicionado", "Sillón / Diván", "Apto camilla",
    ]
    filas = [_encabezados_tabla(encabezados, tamano=7)]
    for c in filas_bd:
        medidas = f"{_medida(c['Largo'])}x{_medida(c['Ancho'])}" if c["Largo"] and c["Ancho"] else "—"
        filas.append([
            str(c["NumeroConsultorio"]), medidas, _si_no(c["Ventana"]), _si_no(c["Balcon"]),
            _si_no(c["PanelVidrioLuzNatural"]), _si_no(c["AireAcondicionado"]), _si_no(c["Sillones"]),
            _si_no(c["AptoCamilla"]),
        ])
    ancho_consultorio = ancho * 0.12
    ancho_medidas = ancho * 0.15
    ancho_resto = (ancho - ancho_consultorio - ancho_medidas) / 6
    anchos = [ancho_consultorio, ancho_medidas] + [ancho_resto] * 6
    tabla = Table(filas, colWidths=anchos, repeatRows=1)
    tabla.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), FUENTE_NEGRITA), ("FONTNAME", (0, 1), (-1, -1), FUENTE),
        ("FONTSIZE", (0, 0), (-1, -1), 8), ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("GRID", (0, 0), (-1, -1), 0.5, "#000000"),
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_NIVEL_1), ("TEXTCOLOR", (0, 0), (-1, 0), "#FFFFFF"),
    ]))
    return tabla


def _detalle_consultorios_edificio(conn: sqlite3.Connection, id_edificio: int, ancho: float) -> list:
    unidades = conn.execute("SELECT IdUnidad, Departamento FROM Unidad WHERE IdEdificio = ?", (id_edificio,)).fetchall()
    unidades = sorted(unidades, key=lambda f: clave_orden_unidad(f["Departamento"]))
    mostrar_unidad = len(unidades) > 1
    story = []
    for u in unidades:
        filas_bd = conn.execute(
            "SELECT NumeroConsultorio, Largo, Ancho, Ventana, Balcon, PanelVidrioLuzNatural, AireAcondicionado, "
            "Sillones, AptoCamilla FROM Consultorio WHERE IdUnidad = ? ORDER BY NumeroConsultorio",
            (u["IdUnidad"],),
        ).fetchall()
        if not filas_bd:
            continue
        if mostrar_unidad:
            story.append(Paragraph(f"<b>Unidad {u['IdUnidad']}</b>", estilo_texto(9, negrita=True)))
            story.append(Spacer(1, 2))
        story.append(_tabla_consultorios(filas_bd, ancho))
        story.append(Spacer(1, 6))
    if not story:
        story.append(Paragraph("Sin consultorios cargados.", estilo_texto(9)))
    return story


def _bloque_edificio_detalles(conn: sqlite3.Connection, edificio: sqlite3.Row, ancho: float, mostrar_encabezado: bool) -> list:
    story = []
    if mostrar_encabezado:
        story.append(encabezado(3, f"Edificio: {edificio['Nombre']}", ancho))
        story.append(Spacer(1, 6))

    style_label = estilo_texto(9, negrita=True)
    story.append(Paragraph("Ubicación", style_label))
    ubicacion = ", ".join(p for p in (edificio["Domicilio"], edificio["DomicilioLocalidad"]) if p)
    story.append(Paragraph(ubicacion or "Sin domicilio cargado.", estilo_texto(9)))
    story.append(Spacer(1, 6))

    story.append(Paragraph("Destino y uso del espacio", style_label))
    story.append(Paragraph(_TEXTO_DESTINO_USO, estilo_texto(9)))
    story.append(Spacer(1, 6))

    story.append(Paragraph("Detalle de las unidades", style_label))
    story.append(Spacer(1, 3))
    story.extend(_tabla_detalle_unidades(conn, edificio["IdEdificio"], ancho))
    story.append(Spacer(1, 6))

    story.append(Paragraph("Detalle de los consultorios", style_label))
    story.append(Spacer(1, 3))
    story.extend(_detalle_consultorios_edificio(conn, edificio["IdEdificio"], ancho))
    return story


def _fotos_agrupadas(conn: sqlite3.Connection, edificios: list[sqlite3.Row], imagenes: list[sqlite3.Row], ancho: float, decimales: int) -> list:
    if not imagenes:
        return [Paragraph("Sin fotos cargadas.", estilo_texto(9))]

    por_edificio: dict[str, dict[int, list]] = {}
    for img in imagenes:
        por_edificio.setdefault(img["NombreEdificio"], {}).setdefault(img["IdUnidadConsultorio"], []).append(img)

    orden_edificios = [e["Nombre"] for e in edificios if e["Nombre"] in por_edificio]
    mostrar_edificio = len(orden_edificios) > 1
    story = []
    for nombre_edificio in orden_edificios:
        unidades = por_edificio[nombre_edificio]
        if mostrar_edificio:
            story.append(encabezado(3, f"Edificio: {nombre_edificio}", ancho))
            story.append(Spacer(1, 6))
        ids_unidad = sorted(unidades, key=lambda id_u: clave_orden_unidad(unidades[id_u][0]["Departamento"]))
        mostrar_unidad = len(unidades) > 1
        for id_unidad in ids_unidad:
            imgs = sorted(unidades[id_unidad], key=lambda i: i["NumeroConsultorio"])
            if mostrar_unidad:
                story.append(Paragraph(f"<b>Unidad {id_unidad}</b>", estilo_texto(9, negrita=True)))
                story.append(Spacer(1, 2))
            story.extend(tabla_fotos(imgs, ancho, mostrar_apto_camilla=True, mostrar_valor=True, decimales=decimales))
    return story


def generar_pdf_propuesta(
    conn: sqlite3.Connection, directorio: str, id_profesional: int | None = None,
    ids_edificio: list[int] | None = None,
) -> str:
    """Genera el PDF de propuesta y devuelve la ruta completa.
    `id_profesional` personaliza "Detalles principales" (profesión de
    interés) cuando se conoce al contacto; sin él genera una propuesta
    genérica del espacio."""
    cfg = conn.execute("SELECT NombreEspacio FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    nombre_espacio = (cfg["NombreEspacio"] if cfg else None) or "Espacio Ramos"
    decimales = decimales_configurados(conn)

    profesional = obtener_repositorio(conn, "Profesional").obtener(id_profesional) if id_profesional else None
    edificios = edificios_incluidos(conn, ids_edificio)
    sufijo = sufijo_localidad(conn, edificios)
    nombre_archivo = f"{nombre_espacio} - Propuesta al profesional{sufijo}.pdf"

    ids_edificio_incluidos = [e["IdEdificio"] for e in edificios]
    ids_consultorio = ids_consultorio_de_edificios(conn, ids_edificio_incluidos)
    imagenes = imagenes_de_consultorios(conn, ids_consultorio)
    anio, mes = parsear_periodo(periodo_actual(conn))
    fecha_titulo = fecha_larga(fecha_actual(conn).isoformat()).replace("/", "-")

    localidades = sorted({e["DomicilioLocalidad"] for e in edificios if e["DomicilioLocalidad"]})
    localidad_texto = " / ".join(localidades)

    n_unidades = 0
    n_consultorios = 0
    if ids_edificio_incluidos:
        placeholders = ", ".join("?" for _ in ids_edificio_incluidos)
        n_unidades = conn.execute(
            f"SELECT COUNT(*) FROM Unidad WHERE IdEdificio IN ({placeholders})", ids_edificio_incluidos,
        ).fetchone()[0]
        n_consultorios = conn.execute(
            f"SELECT COUNT(*) FROM Consultorio c JOIN Unidad u ON u.IdUnidad = c.IdUnidad "
            f"WHERE u.IdEdificio IN ({placeholders})", ids_edificio_incluidos,
        ).fetchone()[0]
    n_detalles = conn.execute("SELECT COUNT(*) FROM DetalleComplementarioPropuesta WHERE Activo = 1").fetchone()[0]
    n_tramos = conn.execute("SELECT COUNT(*) FROM EsquemaDescuentos WHERE Activo = 1").fetchone()[0]
    altura_disponibilidad = altura_estimada_grilla(conn, ids_edificio_incluidos or None)

    altura = (
        8 * cm  # encabezado_espacio + nivel1 "Propuesta al profesional"
        + 1.5 * cm + len(edificios) * 4 * cm  # detalles principales: ubicación/destino por edificio
        + n_unidades * 0.45 * cm + len(edificios) * 1 * cm  # tabla detalle de unidades
        + n_consultorios * 0.4 * cm + len(edificios) * 1 * cm  # tabla detalle de consultorios (agrupada por unidad)
        + 1.5 * cm + (len(imagenes) // 2 + 1) * 7 * cm + len(edificios) * 1 * cm  # fotos
        + altura_disponibilidad  # disponibilidad
        + 1.5 * cm + 5 * 0.5 * cm  # condiciones y forma de reserva
        + 1.5 * cm + len(edificios) * 3 * cm  # valores vigentes
        + 1.5 * cm + n_detalles * 1.8 * cm + ((n_tramos // 9) + 1) * 1.4 * cm  # detalles complementarios
    ) * 1.15

    ruta = os.path.join(directorio, nombre_archivo)
    doc, ancho = crear_documento(ruta, altura=altura)

    story = list(encabezado_espacio(conn, ancho, mostrar_localidad=bool(localidad_texto), localidad=localidad_texto or None))
    story.append(encabezado(1, "Propuesta al profesional", ancho))
    story.append(Spacer(1, 6))

    story.append(encabezado(2, "Detalles principales de la propuesta", ancho))
    story.append(Spacer(1, 6))
    story.extend(_contacto_y_profesion(conn, profesional))
    for i, e in enumerate(edificios):
        if i > 0:
            story.append(Spacer(1, 8))
        story.extend(_bloque_edificio_detalles(conn, e, ancho, mostrar_encabezado=len(edificios) > 1))
    story.append(Spacer(1, 10))

    story.append(encabezado(2, "Fotos de los consultorios", ancho))
    story.append(Spacer(1, 6))
    story.extend(_fotos_agrupadas(conn, edificios, imagenes, ancho, decimales))
    story.append(Spacer(1, 6))

    story.extend(secciones_disponibilidad(
        conn, anio, mes, ancho, fecha_titulo, ids_edificio=ids_edificio_incluidos or None, anonimizar_unidad=True,
    ))

    story.append(Spacer(1, 6))
    story.append(encabezado(2, "Condiciones y forma de reserva", ancho))
    story.append(Spacer(1, 6))
    story.extend(condiciones_forma_reserva(conn))
    story.append(Spacer(1, 10))

    story.append(encabezado(2, "Valores vigentes por hora regular", ancho))
    for e in edificios:
        story.append(Spacer(1, 6))
        story.append(encabezado(3, f"Edificio {e['Nombre']}", ancho))
        story.append(Spacer(1, 6))
        story.extend(matriz_valores_edificio(conn, e["IdEdificio"], ancho, anonimizar_unidad=True))
    story.append(Spacer(1, 10))

    story.append(encabezado(2, "Detalles complementarios de la propuesta", ancho))
    story.append(Spacer(1, 6))
    story.extend(detalles_complementarios_propuesta(conn, ancho))

    doc.build(story)
    return ruta
