"""PDF de Propuesta al profesional (Etapa 7, sección 4.3). Para
profesionales NO activos (categoría C/contacto, o cualquiera que todavía
no tenga reservas confirmadas): a diferencia del PDF de Disponibilidad,
anonimiza las unidades como "Unidad {IdUnidad}" en vez de mostrar el
Departamento real, para no revelar información interna del edificio a
alguien que todavía no forma parte del espacio.

Estructura (4 secciones de nivel 1): "Detalles principales de la
propuesta" (Ubicación, Destino y uso del espacio, Detalle de las
unidades, Detalle de los consultorios) -> "Fotos de los consultorios"
(agrupadas por Unidad, con valor de la hora regular y ✔ Apto camilla) ->
"Disponibilidad de consultorios al {fecha}" (grilla igual que en
Liquidación + "Condiciones y forma de reserva" dinámica + "Valores
vigentes por hora regular") -> "Detalles complementarios de la
propuesta" (editable y ordenable, tabla DetalleComplementarioPropuesta).

Con un solo edificio los sub-ítems de las primeras 3 secciones van en
nivel 2. Con más de uno, se agrega por cada edificio un nivel 2 "{Edificio}
- {Dirección}, {Localidad}" y esos mismos sub-ítems (repetidos por
edificio) bajan a nivel 3 — "Detalles complementarios" nunca se repite
por edificio, es contenido genérico del espacio.

Las unidades se ordenan por IdUnidad ascendente (no por piso/letra como
en Liquidación): con la etiqueta anonimizada "Unidad {N}" lo esperable es
"Unidad 1, Unidad 2, Unidad 3..." en vez de saltar según el piso real.

No incluye "Condiciones y normas" (CondicionNorma): ese contenido queda
reservado al PDF de Liquidación, donde no se superpone con "Detalles
complementarios"."""
from __future__ import annotations

import os
import sqlite3

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from app.negocio.dias import fecha_actual, parsear_periodo, periodo_actual
from app.negocio.formato import fecha_larga, periodo_mm_aaaa
from app.pdf.edificios_pdf import (
    edificios_incluidos,
    hay_multiples_localidades,
    ids_consultorio_de_edificios,
    numero_unidad_en_edificio,
    sufijo_localidad,
    titulo_edificio,
)
from app.negocio.formato import decimales_configurados
from app.pdf.estilos import COLOR_NIVEL_1, FUENTE, FUENTE_NEGRITA, construir_sin_saltos, encabezado, encabezado_espacio, estilo_texto
from app.pdf.fotos_pdf import imagenes_de_consultorios, tabla_fotos
from app.pdf.grilla_pdf import altura_estimada_grilla, secciones_disponibilidad
from app.pdf.valores_pdf import (
    condiciones_forma_reserva,
    detalles_complementarios_propuesta,
    matriz_valores_edificio,
    rango_actualizacion,
)

_TEXTO_DESTINO_USO = (
    "El uso de los consultorios se encuentra dirigido a la realización de terapias individuales de salud "
    "mental, nutrición y similares."
)


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
        SELECT u.IdUnidad, u.SalaDeEspera, u.Cocina, u.Banos, u.WiFi, u.BalconComun,
               u.EntradaProfesionalExclusiva, u.AreaGuardado, u.AreaFumadores,
               (SELECT COUNT(*) FROM Consultorio c WHERE c.IdUnidad = u.IdUnidad) AS CantConsultorios
        FROM Unidad u WHERE u.IdEdificio = ? ORDER BY u.IdUnidad
        """,
        (id_edificio,),
    ).fetchall()
    if not filas_bd:
        return [Paragraph("Sin unidades cargadas.", estilo_texto(9))]

    encabezados = [
        "Unidad", "Consultorios", "Sala de espera", "Cocina", "Baños", "WiFi",
        "Balcón de uso común", "Entrada profesional exclusiva", "Área de guardado", "Área de fumadores",
    ]
    filas = [_encabezados_tabla(encabezados)]
    # Posición dentro de ESTE edificio (1, 2, 3...), no el IdUnidad real
    # (autoincremental global a todo el sistema): la consulta ya viene
    # ordenada por IdUnidad ascendente, así que el índice alcanza.
    for i, f in enumerate(filas_bd):
        filas.append([
            f"Unidad {i + 1}", str(f["CantConsultorios"]), _si_no(f["SalaDeEspera"]), _si_no(f["Cocina"]),
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
    unidades = conn.execute(
        "SELECT IdUnidad FROM Unidad WHERE IdEdificio = ? ORDER BY IdUnidad", (id_edificio,)
    ).fetchall()
    mostrar_unidad = len(unidades) > 1
    story = []
    for i, u in enumerate(unidades):
        filas_bd = conn.execute(
            "SELECT NumeroConsultorio, Largo, Ancho, Ventana, Balcon, PanelVidrioLuzNatural, AireAcondicionado, "
            "Sillones, AptoCamilla FROM Consultorio WHERE IdUnidad = ? ORDER BY NumeroConsultorio",
            (u["IdUnidad"],),
        ).fetchall()
        if not filas_bd:
            continue
        if mostrar_unidad:
            story.append(Paragraph(f"<b>Unidad {i + 1}</b>", estilo_texto(9, negrita=True)))
            story.append(Spacer(1, 2))
        story.append(_tabla_consultorios(filas_bd, ancho))
        story.append(Spacer(1, 6))
    if not story:
        story.append(Paragraph("Sin consultorios cargados.", estilo_texto(9)))
    return story


def _bloque_detalles_principales(conn: sqlite3.Connection, edificio: sqlite3.Row, ancho: float, nivel: int) -> list:
    story = [encabezado(nivel, "Ubicación", ancho), Spacer(1, 6)]
    ubicacion = ", ".join(p for p in (edificio["Domicilio"], edificio["DomicilioLocalidad"]) if p)
    story.append(Paragraph(ubicacion or "Sin domicilio cargado.", estilo_texto(9)))
    story.append(Spacer(1, 8))

    story.append(encabezado(nivel, "Destino y uso del espacio", ancho))
    story.append(Spacer(1, 6))
    story.append(Paragraph(_TEXTO_DESTINO_USO, estilo_texto(9)))
    story.append(Spacer(1, 8))

    story.append(encabezado(nivel, "Detalle de las unidades", ancho))
    story.append(Spacer(1, 6))
    story.extend(_tabla_detalle_unidades(conn, edificio["IdEdificio"], ancho))
    story.append(Spacer(1, 8))

    story.append(encabezado(nivel, "Detalle de los consultorios", ancho))
    story.append(Spacer(1, 6))
    story.extend(_detalle_consultorios_edificio(conn, edificio["IdEdificio"], ancho))
    return story


def _bloque_fotos(
    imagenes_edificio: list[sqlite3.Row], ancho: float, nivel: int, decimales: int, numeros_unidad: dict[int, int],
) -> list:
    if not imagenes_edificio:
        return [Paragraph("Sin fotos cargadas.", estilo_texto(9))]
    por_unidad: dict[int, list] = {}
    for img in imagenes_edificio:
        por_unidad.setdefault(img["IdUnidadConsultorio"], []).append(img)

    story = []
    # Ordenar por la posición real dentro del edificio (no por IdUnidad):
    # una unidad sin fotos no debe "correr" el número de las siguientes.
    for id_unidad in sorted(por_unidad, key=lambda id_u: numeros_unidad[id_u]):
        imgs = sorted(por_unidad[id_unidad], key=lambda i: i["NumeroConsultorio"])
        story.append(encabezado(nivel, f"Unidad {numeros_unidad[id_unidad]}", ancho))
        story.append(Spacer(1, 6))
        story.extend(tabla_fotos(imgs, ancho, mostrar_apto_camilla=True, mostrar_valor=True, decimales=decimales))
    return story


def _bloque_disponibilidad(
    conn: sqlite3.Connection, edificio: sqlite3.Row, anio: int, mes: int, ancho: float, fecha_titulo: str,
    nivel: int, mostrar_encabezado_grid: bool, desde: str, hasta: str,
) -> list:
    story = list(secciones_disponibilidad(
        conn, anio, mes, ancho, fecha_titulo, ids_edificio=[edificio["IdEdificio"]], anonimizar_unidad=True,
        mostrar_titulo=False, mostrar_encabezado_edificio=mostrar_encabezado_grid,
    ))

    story.append(encabezado(nivel, "Condiciones y forma de reserva", ancho))
    story.append(Spacer(1, 6))
    story.extend(condiciones_forma_reserva(conn))
    story.append(Spacer(1, 10))

    titulo_valores = (
        f"Valores vigentes por hora regular para el período comprendido entre "
        f"{periodo_mm_aaaa(desde)} y {periodo_mm_aaaa(hasta)}"
    )
    story.append(encabezado(nivel, titulo_valores, ancho))
    story.append(Spacer(1, 6))
    numeros_unidad = numero_unidad_en_edificio(conn, edificio["IdEdificio"])
    story.extend(matriz_valores_edificio(
        conn, edificio["IdEdificio"], ancho, anonimizar_unidad=True, numeros_unidad=numeros_unidad,
    ))
    return story


def generar_pdf_propuesta(
    conn: sqlite3.Connection, directorio: str, ids_edificio: list[int] | None = None,
) -> str:
    """Genera el PDF de propuesta y devuelve la ruta completa. Es la misma
    propuesta genérica del espacio para cualquier profesional interesado
    (no se personaliza por contacto puntual)."""
    cfg = conn.execute("SELECT NombreEspacio FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    nombre_espacio = (cfg["NombreEspacio"] if cfg else None) or "Espacio Ramos"
    decimales = decimales_configurados(conn)

    edificios = edificios_incluidos(conn, ids_edificio)
    multi = len(edificios) > 1
    sufijo = sufijo_localidad(conn, edificios)
    nombre_archivo = f"Propuesta {nombre_espacio} Consultorios{sufijo}.pdf"

    ids_edificio_incluidos = [e["IdEdificio"] for e in edificios]
    ids_consultorio = ids_consultorio_de_edificios(conn, ids_edificio_incluidos)
    imagenes = imagenes_de_consultorios(conn, ids_consultorio)
    anio, mes = parsear_periodo(periodo_actual(conn))
    fecha_titulo = fecha_larga(fecha_actual(conn).isoformat()).replace("/", "-")
    desde, hasta = rango_actualizacion(conn, periodo_actual(conn))

    mostrar_localidad = hay_multiples_localidades(conn)
    localidades = sorted({e["DomicilioLocalidad"] for e in edificios if e["DomicilioLocalidad"]})
    localidad_texto = " / ".join(localidades) if mostrar_localidad else ""

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
    n_ed = len(edificios)
    n_unidades_con_fotos = len({(i["NombreEdificio"], i["IdUnidadConsultorio"]) for i in imagenes})

    altura = (
        6 * cm  # encabezado_espacio (logo + línea)
        + 1.5 * cm + n_ed * 1 * cm  # nivel1 "Detalles principales" + wrapper nivel2 por edificio (si multi)
        + n_ed * 3 * cm  # Ubicación + Destino y uso por edificio
        + n_unidades * 0.45 * cm + n_ed * 1 * cm  # tabla detalle de unidades
        + n_consultorios * 0.4 * cm + n_ed * 1 * cm  # tabla detalle de consultorios
        + 1.5 * cm + n_ed * 1 * cm  # nivel1 "Fotos de los consultorios" + wrapper por edificio
        + (len(imagenes) // 2 + 1) * 7 * cm + n_unidades_con_fotos * 1 * cm  # fotos + "Unidad N"
        + 1.5 * cm + n_ed * 1 * cm  # nivel1 "Disponibilidad..." + wrapper por edificio
        + altura_disponibilidad  # grillas (ya suma por edificio)
        + n_ed * (1.5 * cm + 5 * 0.5 * cm)  # condiciones y forma de reserva (por edificio si multi)
        + n_ed * (1.5 * cm + 3 * cm)  # valores vigentes (por edificio)
        + 1.5 * cm + n_detalles * 1.8 * cm + ((n_tramos // 9) + 1) * 1.4 * cm  # detalles complementarios
    ) * 1.15

    def _construir_story(ancho: float) -> list:
        story = list(encabezado_espacio(
            conn, ancho, mostrar_localidad=mostrar_localidad, localidad=localidad_texto or None,
        ))

        # --------------------------------------------------- Detalles principales
        story.append(encabezado(1, "Detalles principales de la propuesta", ancho))
        story.append(Spacer(1, 8))
        if multi:
            for e in edificios:
                story.append(encabezado(2, titulo_edificio(e), ancho))
                story.append(Spacer(1, 6))
                story.extend(_bloque_detalles_principales(conn, e, ancho, nivel=3))
                story.append(Spacer(1, 10))
        else:
            story.extend(_bloque_detalles_principales(conn, edificios[0], ancho, nivel=2))
        story.append(Spacer(1, 10))

        # ----------------------------------------------------------------- Fotos
        story.append(encabezado(1, "Fotos de los consultorios", ancho))
        story.append(Spacer(1, 8))
        if multi:
            for e in edificios:
                imagenes_ed = [i for i in imagenes if i["NombreEdificio"] == e["Nombre"]]
                if not imagenes_ed:
                    continue
                numeros_unidad = numero_unidad_en_edificio(conn, e["IdEdificio"])
                story.append(encabezado(2, titulo_edificio(e), ancho))
                story.append(Spacer(1, 6))
                story.extend(_bloque_fotos(imagenes_ed, ancho, nivel=3, decimales=decimales, numeros_unidad=numeros_unidad))
                story.append(Spacer(1, 10))
        else:
            numeros_unidad = numero_unidad_en_edificio(conn, edificios[0]["IdEdificio"])
            story.extend(_bloque_fotos(imagenes, ancho, nivel=2, decimales=decimales, numeros_unidad=numeros_unidad))
        story.append(Spacer(1, 10))

        # -------------------------------------------------------- Disponibilidad
        story.append(encabezado(1, f"Disponibilidad de consultorios al {fecha_titulo}", ancho))
        story.append(Spacer(1, 8))
        if multi:
            for e in edificios:
                story.append(encabezado(2, titulo_edificio(e), ancho))
                story.append(Spacer(1, 6))
                story.extend(_bloque_disponibilidad(
                    conn, e, anio, mes, ancho, fecha_titulo, nivel=3,
                    mostrar_encabezado_grid=False, desde=desde, hasta=hasta,
                ))
                story.append(Spacer(1, 10))
        else:
            # Con un solo edificio, repetir "Edificio {Nombre}" arriba de
            # la grilla es redundante (no hay otro del que distinguirlo).
            story.extend(_bloque_disponibilidad(
                conn, edificios[0], anio, mes, ancho, fecha_titulo, nivel=2,
                mostrar_encabezado_grid=False, desde=desde, hasta=hasta,
            ))
        story.append(Spacer(1, 10))

        # ------------------------------------------------ Detalles complementarios
        story.append(encabezado(1, "Detalles complementarios de la propuesta", ancho))
        story.append(Spacer(1, 8))
        story.extend(detalles_complementarios_propuesta(conn, ancho))
        return story

    ruta = os.path.join(directorio, nombre_archivo)
    construir_sin_saltos(ruta, _construir_story, altura)
    return ruta


def generar_pdfs_propuesta_por_localidad(conn: sqlite3.Connection, directorio: str) -> list[str]:
    """Un PDF de Propuesta por cada localidad con edificios cargados: nunca
    mezcla edificios de distintas localidades en el mismo archivo. Los
    edificios sin localidad cargada quedan agrupados aparte, en un único
    archivo sin sufijo de localidad. Devuelve las rutas generadas."""
    filas = conn.execute("SELECT IdEdificio, DomicilioLocalidad FROM Edificio").fetchall()
    grupos: dict[str | None, list[int]] = {}
    for f in filas:
        grupos.setdefault(f["DomicilioLocalidad"], []).append(f["IdEdificio"])
    return [generar_pdf_propuesta(conn, directorio, ids_edificio=ids) for ids in grupos.values()]
