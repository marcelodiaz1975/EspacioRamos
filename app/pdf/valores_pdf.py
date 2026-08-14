"""Valores vigentes de consultorios y esquema de descuentos, compartidos
por el PDF de Liquidación y el de Propuesta (secciones 4.5/4.3)."""
from __future__ import annotations

import json
import sqlite3

from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from app.negocio.formato import hora_fmt
from app.negocio.formato import decimales_configurados, formatear_moneda
from app.pdf.estilos import COLOR_NIVEL_1, FUENTE_NEGRITA, clave_orden_unidad, encabezado, estilo_texto


def _hasta_por_frecuencia(desde: str, meses_actualizacion: list[int]) -> str:
    """Último mes en que el valor de `desde` sigue vigente: el mes
    anterior al próximo mes de actualización programado (envolviendo al
    año siguiente si hace falta). Ej: actualización bimestral en meses
    pares, `desde`="2026-08" -> próxima actualización en 10, vigente
    hasta "2026-09". Semestral en enero/julio, `desde`="2026-07" ->
    próxima actualización en 01/2027, vigente hasta "2026-12"."""
    anio, mes = (int(p) for p in desde.split("-"))
    meses_ordenados = sorted(set(meses_actualizacion))
    siguientes = [m for m in meses_ordenados if m > mes]
    if siguientes:
        proximo_mes, proximo_anio = siguientes[0], anio
    else:
        proximo_mes, proximo_anio = meses_ordenados[0], anio + 1
    mes_hasta, anio_hasta = proximo_mes - 1, proximo_anio
    if mes_hasta == 0:
        mes_hasta, anio_hasta = 12, anio_hasta - 1
    return f"{anio_hasta:04d}-{mes_hasta:02d}"


def rango_actualizacion(conn: sqlite3.Connection, periodo: str) -> tuple[str, str]:
    """(desde, hasta) — el período del último aumento aplicado hasta
    `periodo` (o `periodo` mismo si nunca hubo uno) como `desde`, y el
    último mes en que ese valor sigue vigente según
    `Configuracion.MesesPeriodoActualizacion` como `hasta`. Si no hay
    frecuencia configurada, `hasta` queda igual a `desde` — mostrar un
    rango inventado sería peor que no mostrar rango."""
    fila = conn.execute(
        "SELECT MAX(Periodo) AS p FROM AumentoAplicado WHERE Periodo <= ?", (periodo,)
    ).fetchone()
    desde = fila["p"] if fila and fila["p"] else periodo

    cfg = conn.execute(
        "SELECT MesesPeriodoActualizacion FROM Configuracion WHERE IdConfiguracion = 1"
    ).fetchone()
    meses = json.loads(cfg["MesesPeriodoActualizacion"]) if cfg and cfg["MesesPeriodoActualizacion"] else []
    hasta = _hasta_por_frecuencia(desde, meses) if meses else desde
    return desde, hasta


def matriz_valores_edificio(
    conn: sqlite3.Connection, id_edificio: int, ancho: float, anonimizar_unidad: bool = False,
    numeros_unidad: dict[int, int] | None = None,
) -> list:
    """Tabla Unidad (filas) x Consultorio N (columnas) -> ValorHoraRegularActual,
    con "—" para los números de consultorio que no existen en esa unidad.
    `anonimizar_unidad` muestra "Unidad {N}" en vez del Departamento real
    (sección 4.3, PDF de Propuesta, que va a profesionales NO activos); `N`
    es la posición de la unidad DENTRO de su edificio (`numeros_unidad`,
    ver `edificios_pdf.numero_unidad_en_edificio`) — no el IdUnidad real,
    que es un autoincremental global a todo el sistema. Si no se pasa
    `numeros_unidad` con `anonimizar_unidad=True` se calcula acá mismo a
    partir del orden de IdUnidad de esta misma consulta."""
    decimales = decimales_configurados(conn)
    # Anonimizado (Propuesta): orden por número de unidad ascendente, no
    # por piso — la etiqueta "Unidad N" no tiene piso/letra real que
    # ordenar, y así queda "Unidad 1, Unidad 2, Unidad 3..." en vez de
    # saltar según el piso real de cada una.
    orden_sql = "u.IdUnidad" if anonimizar_unidad else "u.Departamento"
    filas_bd = conn.execute(
        f"""
        SELECT u.IdUnidad, u.Departamento, c.NumeroConsultorio, c.ValorHoraRegularActual
        FROM Consultorio c JOIN Unidad u ON u.IdUnidad = c.IdUnidad
        WHERE u.IdEdificio = ? ORDER BY {orden_sql}, c.NumeroConsultorio
        """,
        (id_edificio,),
    ).fetchall()
    if anonimizar_unidad and numeros_unidad is None:
        numeros_unidad = {}
        for f in filas_bd:
            numeros_unidad.setdefault(f["IdUnidad"], len(numeros_unidad) + 1)
    por_unidad: dict[str, dict[int, float]] = {}
    for f in filas_bd:
        etiqueta = f"Unidad {numeros_unidad[f['IdUnidad']]}" if anonimizar_unidad else f["Departamento"]
        por_unidad.setdefault(etiqueta, {})[f["NumeroConsultorio"]] = f["ValorHoraRegularActual"]
    max_consultorios = max((max(v.keys()) for v in por_unidad.values()), default=0)
    if max_consultorios == 0:
        return [Paragraph("Sin consultorios cargados.", estilo_texto(9))]

    encabezado_fila = ["Unidad"] + [f"Consul. {n}" for n in range(1, max_consultorios + 1)]
    filas = [encabezado_fila]
    # Anonimizado: ya vino ordenado por IdUnidad de la consulta SQL (dict
    # preserva orden de inserción). Sin anonimizar (Liquidación): piso
    # ascendente (EP/PB como si fuera 0, arriba de todo) y, a igualdad de
    # piso, letra del departamento alfabética — mismo criterio que las
    # grillas de disponibilidad.
    unidades_ordenadas = list(por_unidad) if anonimizar_unidad else sorted(por_unidad, key=clave_orden_unidad)
    for unidad in unidades_ordenadas:
        valores = por_unidad[unidad]
        filas.append(
            [unidad]
            + [formatear_moneda(valores[n], decimales) if n in valores else "—" for n in range(1, max_consultorios + 1)]
        )

    ancho_unidad = ancho * 0.18
    ancho_col = (ancho - ancho_unidad) / max_consultorios
    tabla = Table(filas, colWidths=[ancho_unidad] + [ancho_col] * max_consultorios, repeatRows=1)
    tabla.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), FUENTE_NEGRITA),
        ("FONTSIZE", (0, 0), (-1, -1), 8), ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"), ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, "#000000"), ("BACKGROUND", (0, 0), (-1, 0), COLOR_NIVEL_1),
        ("TEXTCOLOR", (0, 0), (-1, 0), "#FFFFFF"), ("BACKGROUND", (0, 1), (0, -1), "#F0F0F0"),
    ]))
    return [tabla]


def bloques_esquema_descuentos(conn: sqlite3.Connection, ancho: float) -> list:
    """Bloques horizontales de a 9 tramos ("Hs. semanales" / "Descuento").

    Si la cantidad de tramos no es múltiplo de 9, la última fila queda con
    menos columnas que las anteriores — para que las filas se vean parejas
    se completa con tramos "de relleno" que repiten el % tope (el de más
    horas semanales), incrementando "Hasta Nhs" con el mismo paso que ya
    usan los tramos reales. Así, si en el futuro se agregan o sacan
    tramos, la última fila se sigue completando sola."""
    tramos = conn.execute(
        "SELECT * FROM EsquemaDescuentos WHERE Activo = 1 ORDER BY HorasSemanalesDesde"
    ).fetchall()
    if not tramos:
        return [Paragraph("Sin esquema de descuentos configurado.", estilo_texto(9))]

    por_bloque = 9
    faltan = (-len(tramos)) % por_bloque
    if faltan:
        paso = tramos[-1]["HorasSemanalesHasta"] - tramos[-2]["HorasSemanalesHasta"] if len(tramos) >= 2 else 2
        tope_pct = max(t["PorcentajeDescuento"] for t in tramos)
        ultimo_hasta = tramos[-1]["HorasSemanalesHasta"]
        relleno = []
        for _ in range(faltan):
            ultimo_hasta += paso
            relleno.append({"HorasSemanalesHasta": ultimo_hasta, "PorcentajeDescuento": tope_pct})
        tramos = list(tramos) + relleno

    story = []
    for inicio in range(0, len(tramos), por_bloque):
        grupo = tramos[inicio:inicio + por_bloque]
        fila_horas = ["Hs. semanales"] + [f"Hasta {t['HorasSemanalesHasta']:g}hs" for t in grupo]
        fila_desc = ["Descuento"] + [f"{t['PorcentajeDescuento']:g}%" for t in grupo]
        n = len(grupo)
        ancho_col = ancho / (n + 1)
        tabla = Table([fila_horas, fila_desc], colWidths=[ancho_col] * (n + 1))
        tabla.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), FUENTE_NEGRITA), ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, "#000000"),
            ("BACKGROUND", (0, 0), (0, -1), COLOR_NIVEL_1), ("TEXTCOLOR", (0, 0), (0, -1), "#FFFFFF"),
            ("BACKGROUND", (1, 0), (-1, 0), COLOR_NIVEL_1), ("TEXTCOLOR", (1, 0), (-1, 0), "#FFFFFF"),
        ]))
        story.append(tabla)
        story.append(Spacer(1, 4))
    return story


def condiciones_normas(conn: sqlite3.Connection) -> list:
    """Los 21 puntos editables de "Condiciones y normas" (CondicionNorma),
    numerados "N) TÍTULO:" en mayúsculas (PDF de Liquidación)."""
    condiciones = conn.execute("SELECT * FROM CondicionNorma WHERE Activo = 1 ORDER BY Numero").fetchall()
    style = estilo_texto(9)
    return [Paragraph(f"<b>{c['Numero']}) {c['Titulo'].upper()}:</b> {c['Texto']}", style) for c in condiciones]


def condiciones_forma_reserva(conn: sqlite3.Connection) -> list:
    """"Condiciones y forma de reserva" del PDF de Propuesta (sección
    4.3): los dos puntos que dependen de datos configurados de verdad
    (bloques rígidos activos, límites de la grilla horaria) se arman
    dinámicamente a partir de `BloqueRigido`/`Configuracion` para no
    desactualizarse si esos valores cambian; el resto son reglas fijas
    del sistema."""
    style = estilo_texto(9)
    story = [Paragraph("* No hay un mínimo de horas a reservar.", style)]

    bloques = conn.execute("SELECT HoraInicio, HoraFin FROM BloqueRigido WHERE Activo = 1 ORDER BY HoraInicio").fetchall()
    if bloques:
        rangos = [f"{hora_fmt(b['HoraInicio'])[:-2]} a {hora_fmt(b['HoraFin'])}" for b in bloques]
        texto_rangos = (", de ".join(rangos[:-1]) + " y de " + rangos[-1]) if len(rangos) > 1 else rangos[0]
        story.append(Paragraph(
            f"* Los bloques de {texto_rangos} se deben reservar enteros sin fraccionar, el resto de los "
            f"horarios sin limitaciones.", style,
        ))

    story.append(Paragraph("* Las horas reservadas en un mismo consultorio deben ser consecutivas.", style))

    cfg = conn.execute("SELECT HoraInicioGrilla, HoraFinGrilla FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    if cfg:
        story.append(Paragraph(
            f"* Los horarios de las {hora_fmt(cfg['HoraInicioGrilla'])} y de las "
            f"{hora_fmt(cfg['HoraFinGrilla'] - 1)} también están disponibles.", style,
        ))

    story.append(Paragraph(
        "* De acuerdo a la disponibilidad al momento, también se pueden reservar horas aisladas por solo una "
        "única vez.", style,
    ))
    return story


def _sustituciones_detalles_complementarios(conn: sqlite3.Connection) -> dict[str, str]:
    """Valores para los placeholders que puede llevar el `Texto` de un
    ítem editable: "{frecuencia}" (el ítem "Ajuste de valores" toma la
    frecuencia real configurada, no queda hardcodeada) y "{contacto}" (el
    ítem "Contacto" arma "Nombre - Celular - Email" del responsable
    marcado como contacto principal)."""
    cfg = conn.execute(
        "SELECT FrecuenciaActualizacionValores FROM Configuracion WHERE IdConfiguracion = 1"
    ).fetchone()
    frecuencia = ((cfg["FrecuenciaActualizacionValores"] if cfg else None) or "periódica").lower()

    resp = conn.execute(
        "SELECT Nombre, Celular, Email FROM Responsable WHERE EsContactoPrincipal = 1 AND Activo = 1 LIMIT 1"
    ).fetchone()
    contacto = (
        " - ".join(p for p in (resp["Nombre"], resp["Celular"], resp["Email"]) if p)
        if resp else "Sin datos de contacto cargados."
    )
    return {"{frecuencia}": frecuencia, "{contacto}": contacto}


def detalles_complementarios_propuesta(conn: sqlite3.Connection, ancho: float) -> list:
    """Los ítems editables y ordenables de "Detalles complementarios de la
    propuesta" (DetalleComplementarioPropuesta, sección 4.3), cada uno con
    su propio título de nivel 2. El ítem de descuentos es el único con
    contenido tabular: además del texto, muestra debajo el esquema de
    descuentos vigente (EsquemaDescuentos)."""
    items = conn.execute("SELECT * FROM DetalleComplementarioPropuesta WHERE Activo = 1 ORDER BY Orden").fetchall()
    sustituciones = _sustituciones_detalles_complementarios(conn)
    story = []
    for item in items:
        story.append(encabezado(2, item["Titulo"], ancho))
        story.append(Spacer(1, 4))
        texto = item["Texto"]
        for clave, valor in sustituciones.items():
            texto = texto.replace(clave, valor)
        story.append(Paragraph(texto, estilo_texto(9)))
        if "descuentos" in item["Titulo"].strip().lower():
            story.append(Spacer(1, 4))
            story.extend(bloques_esquema_descuentos(conn, ancho))
        story.append(Spacer(1, 8))
    return story
