"""Grilla completa de disponibilidad hora por hora, agrupada por edificio
(sección 4.2) — reusada tanto en el PDF de Disponibilidad standalone
(Etapa 7, sección 4.4) como en la sección "Disponibilidad" embebida en el
PDF de Liquidación (sección 4.5), siguiendo el modelo real: filas =
Tipo de bloque (Rígido/Flexible, según BloqueRigido) + Horario, columnas
= Día > Unidad. Las celdas "naranja" (un solo consultorio disponible SIN
ventana) se pintan del mismo amarillo que "amarillo" (ya lo hace el
`BACKGROUND` de la celda) con un círculo naranja encima (`_CeldaDosTonos`)
para distinguirlas sin agregar un quinto color — reemplaza al texto "S/V"
que se usaba antes, que con muchas unidades por edificio quedaba
demasiado chico para leerse."""
from __future__ import annotations

import sqlite3

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import Flowable, KeepTogether, Paragraph, Spacer, Table, TableStyle

from app.negocio.dias import DIAS_SEMANA
from app.negocio.formato import hora_fmt
from app.negocio.grilla import calcular_grilla
from app.pdf.estilos import (
    COLOR_AMARILLO,
    COLOR_NARANJA,
    COLOR_NIVEL_1,
    COLOR_ROJO,
    COLOR_VERDE,
    FUENTE,
    FUENTE_NEGRITA,
    MARGEN,
    clave_orden_unidad,
    encabezado,
    estilo_texto,
)
from app.pdf.estilos import partir_etiqueta_unidad as _partir_etiqueta_unidad

DIAS_GRILLA_DEFAULT = DIAS_SEMANA[:6]  # Lunes a Sábado
_COLOR_CELDA = {"verde": COLOR_VERDE, "amarillo": COLOR_AMARILLO, "naranja": COLOR_AMARILLO, "rojo": COLOR_ROJO}
_GROSOR_GRUESO = 1.3  # líneas estructurales (días, rígido/flexible, marcos de encabezado)
_DIAMETRO_DOS_TONOS_MAX = 6  # tamaño "cómodo" del círculo naranja cuando hay lugar de sobra


class _CeldaDosTonos(Flowable):
    """Círculo naranja centrado sobre el amarillo de fondo de la celda —
    referencia de "un solo consultorio disponible sin ventana". Tamaño
    fijo (no depende del `availHeight`/`availWidth` que le pase la tabla
    al medir: usar esos valores directamente haría que una sola pasada de
    medición con alto "infinito" infle la fila entera)."""

    def __init__(self, diametro: float = _DIAMETRO_DOS_TONOS_MAX):
        super().__init__()
        self.diametro = diametro

    def wrap(self, availWidth, availHeight):
        return self.diametro, self.diametro

    def draw(self):
        radio = self.diametro / 2
        self.canv.setFillColor(COLOR_NARANJA)
        self.canv.circle(radio, radio, radio, stroke=0, fill=1)


def _tipo_bloque_por_hora(conn: sqlite3.Connection, horas: list[int]) -> dict[int, str]:
    """Un BloqueRigido activo cubre esa hora para todos los días (esta
    grilla no distingue rígido/flexible por día, solo por horario)."""
    filas = conn.execute("SELECT HoraInicio, HoraFin FROM BloqueRigido WHERE Activo = 1").fetchall()
    return {h: ("Rígido" if any(f["HoraInicio"] <= h < f["HoraFin"] for f in filas) else "Flexible") for h in horas}


def _unidades_por_edificio(conn: sqlite3.Connection, ids_edificio: list[int] | None) -> list[sqlite3.Row]:
    if ids_edificio:
        placeholders = ", ".join("?" for _ in ids_edificio)
        return conn.execute(
            f"""
            SELECT u.IdUnidad, u.Departamento, e.IdEdificio, e.Nombre AS NombreEdificio
            FROM Unidad u JOIN Edificio e ON e.IdEdificio = u.IdEdificio
            WHERE e.IdEdificio IN ({placeholders})
            ORDER BY e.Nombre, u.Departamento
            """,
            ids_edificio,
        ).fetchall()
    return conn.execute(
        """
        SELECT u.IdUnidad, u.Departamento, e.IdEdificio, e.Nombre AS NombreEdificio
        FROM Unidad u JOIN Edificio e ON e.IdEdificio = u.IdEdificio
        ORDER BY e.Nombre, u.Departamento
        """
    ).fetchall()


def _tamano_que_entra(
    textos: list[str], ancho_disponible: float, tamano_max: int = 10, tamano_min: int = 5,
    fuente: str = FUENTE_NEGRITA,
) -> int:
    """El tamaño de fuente más grande (dentro de [tamano_min, tamano_max])
    con el que TODOS los textos entran en una línea sin envolver — se mide
    el ancho real de cada uno en vez de asumir que el más largo por
    cantidad de caracteres es el más ancho (ej. "EP" es más ancho que "15"
    aunque tengan la misma longitud, las letras son más anchas que los
    dígitos en negrita). Envolver "15" en "1"/"5" a mitad de palabra se ve
    peor que dejarlo un poco más chico pero legible en una sola línea.
    `fuente` debe coincidir con la fuente real de renderizado — medir con
    una fuente distinta a la usada al dibujar puede sub o sobre-estimar
    cuánto entra."""
    if not textos:
        return tamano_max
    for tamano in range(tamano_max, tamano_min - 1, -1):
        ancho_maximo = max(stringWidth(t, fuente, tamano) for t in textos)
        if ancho_maximo <= ancho_disponible * 0.85:
            return tamano
    return tamano_min


def _tabla_grilla_edificio(
    conn: sqlite3.Connection, unidades: list[sqlite3.Row], grilla: dict, horas: list[int], ancho: float,
    anonimizar_unidad: bool = False,
) -> Table:
    dias = DIAS_GRILLA_DEFAULT
    tipo_por_hora = _tipo_bloque_por_hora(conn, horas)

    n_unidades = len(unidades)
    ancho_tipo, ancho_horario = ancho * 0.08, ancho * 0.06
    ancho_restante = ancho - ancho_tipo - ancho_horario
    n_cols_datos = max(len(dias) * n_unidades, 1)
    ancho_col = ancho_restante / n_cols_datos

    def _partes_etiqueta(indice: int, u: sqlite3.Row) -> tuple[str, str]:
        if anonimizar_unidad:
            # Posición 1-based DENTRO de este edificio (no el IdUnidad
            # real, que es un autoincremental global a todo el sistema):
            # `unidades` ya viene ordenada por IdUnidad ascendente cuando
            # anonimizar_unidad (ver `secciones_disponibilidad`), así que
            # el índice en la lista es exactamente esa posición.
            return str(indice + 1), ""
        return _partir_etiqueta_unidad(u["Departamento"])

    # Con muchas unidades por edificio la columna por consultorio se vuelve
    # angosta (varios edificios reales tienen 4+ unidades) — una celda de
    # texto plano no ajusta el contenido y termina desbordando sobre la
    # celda vecina, así que el piso y la letra van en un Paragraph propio
    # cada uno (una fila para cada uno). El tamaño de fuente se calcula
    # para que el texto más largo entre en una sola línea — más grande
    # cuando hay lugar, sin llegar a partir "15" en "1"/"5".
    partes = [_partes_etiqueta(i, u) for i, u in enumerate(unidades)]
    textos_etiqueta = [p for par in partes for p in par if p]
    # -2: LEFTPADDING+RIGHTPADDING de la celda. Sin negrita y en blanco
    # (fondo azul) — la medición usa la misma fuente con la que se dibuja.
    tamano_etiqueta = _tamano_que_entra(textos_etiqueta, ancho_col - 2, fuente=FUENTE)
    style_etiqueta = estilo_texto(tamano_etiqueta, negrita=False, alignment=TA_CENTER, textColor=colors.white)

    # El día de la semana usa la palabra más larga ("MIÉRCOLES") para
    # calcular el tamaño que entra en el ancho de todo su bloque de
    # columnas (mismo ancho para los 6 días, ya que unidades x ancho_col
    # se cancela). El círculo naranja de "un solo consultorio sin ventana"
    # se achica si la columna de una unidad es más angosta que su tamaño
    # cómodo (más unidades por edificio).
    ancho_dia = ancho_restante / len(dias)
    tamano_dia = _tamano_que_entra([d.upper() for d in dias], ancho_dia - 2, tamano_max=14, tamano_min=6)
    diametro_dos_tonos = min(ancho_col - 2, _DIAMETRO_DOS_TONOS_MAX)

    fila_dias = ["Tipo\nBloque", "Horario"] + [d.upper() for d in dias for _ in unidades]
    fila_unidad_label = ["", ""] + ["UNIDAD" for _ in dias for _ in unidades]
    fila_piso = ["", ""] + [Paragraph(par[0], style_etiqueta) for _ in dias for par in partes]
    fila_letra = ["", ""] + [Paragraph(par[1], style_etiqueta) for _ in dias for par in partes]
    filas = [fila_dias, fila_unidad_label, fila_piso, fila_letra]

    fondos = []
    spans = []
    limites_grupo: list[int] = []  # última fila de cada grupo rígido/flexible (para línea gruesa + caja)
    inicios_grupo: list[int] = []
    tipo_anterior, inicio_grupo = None, None
    for fila_idx, h in enumerate(horas, start=4):
        fila = ["", hora_fmt(h)]
        tipo = tipo_por_hora[h]
        if tipo != tipo_anterior:
            if tipo_anterior is not None:
                spans.append(("SPAN", (0, inicio_grupo), (0, fila_idx - 1)))
                limites_grupo.append(fila_idx - 1)
                inicios_grupo.append(inicio_grupo)
            inicio_grupo, tipo_anterior = fila_idx, tipo
        for dia in dias:
            for u in unidades:
                color = grilla.get((u["IdUnidad"], dia, h), "rojo")
                fila.append(_CeldaDosTonos(diametro_dos_tonos) if color == "naranja" else "")
                fondos.append((color, fila_idx, len(fila) - 1))
        filas.append(fila)
    spans.append(("SPAN", (0, inicio_grupo), (0, len(horas) + 3)))
    inicios_grupo.append(inicio_grupo)

    for fila_idx, h in enumerate(horas, start=4):
        filas[fila_idx][0] = tipo_por_hora[h]

    col_widths = [ancho_tipo, ancho_horario] + [ancho_col] * n_cols_datos
    tabla = Table(filas, colWidths=col_widths, repeatRows=4)
    ultima_fila = len(horas) + 3

    estilo = [
        ("FONTNAME", (0, 0), (-1, -1), FUENTE_NEGRITA),
        ("FONTSIZE", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.3, "#999999"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        # El padding por defecto de reportlab (6pt a cada lado) se come casi
        # toda una columna angosta (edificios con 4+ unidades) — achicarlo
        # le devuelve ese espacio al texto del piso/letra.
        ("LEFTPADDING", (0, 0), (-1, -1), 1),
        ("RIGHTPADDING", (0, 0), (-1, -1), 1),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("BACKGROUND", (0, 0), (1, 3), COLOR_NIVEL_1),
        ("TEXTCOLOR", (0, 0), (1, 3), "#FFFFFF"),
        ("BACKGROUND", (2, 0), (-1, 0), COLOR_NIVEL_1),
        ("TEXTCOLOR", (2, 0), (-1, 0), "#FFFFFF"),
        ("FONTSIZE", (2, 0), (-1, 0), tamano_dia),
        ("BACKGROUND", (2, 1), (-1, 3), COLOR_NIVEL_1),
        ("TEXTCOLOR", (2, 1), (-1, 3), "#FFFFFF"),
        # El divisor entre la fila de piso y la de letra se pinta del mismo
        # azul que el fondo para que quede invisible — más grueso que la
        # línea fina de la GRID que tapa (dibujada antes, debajo), para que
        # el antialiasing de esa línea no deje un resto visible del gris.
        ("LINEBELOW", (2, 2), (-1, 2), 1.2, COLOR_NIVEL_1),
        # "UNIDAD" pegado a la fila de piso/letra de abajo (no solo abajo
        # dentro de su propia celda, que ya era tan ajustada que el VALIGN
        # solo no se notaba): más padding arriba (la aleja del día) y casi
        # nada abajo (la acerca al piso).
        ("VALIGN", (2, 1), (-1, 1), "BOTTOM"),
        ("TOPPADDING", (2, 1), (-1, 1), 5),
        ("BOTTOMPADDING", (2, 1), (-1, 1), 0),
        # "Tipo Bloque"/"Horario" combinan las 4 filas de encabezado (mismo
        # alto que Día/Unidad/Piso/Letra) en vez de quedar ancladas arriba.
        ("SPAN", (0, 0), (0, 3)),
        ("SPAN", (1, 0), (1, 3)),
    ]
    idx = 2
    for dia in dias:
        estilo.append(("SPAN", (idx, 0), (idx + n_unidades - 1, 0)))
        estilo.append(("SPAN", (idx, 1), (idx + n_unidades - 1, 1)))
        idx += n_unidades
    estilo.extend(spans)
    for color, fila, col in fondos:
        estilo.append(("BACKGROUND", (col, fila), (col, fila), _COLOR_CELDA[color]))

    # Líneas estructurales más gruesas que la grilla fina: el marco de
    # Tipo Bloque/Horario, el marco de Día/Unidad/Piso/Letra, un divisor
    # por cada día, un divisor entre cada bloque rígido/flexible, una caja
    # por cada grupo Rígido/Flexible con sus horarios (columnas 0-1), y un
    # marco grueso alrededor de toda la grilla (incluye el borde inferior
    # del último bloque flexible, que si no queda sin remarcar).
    estilo.append(("BOX", (0, 0), (1, 3), _GROSOR_GRUESO, "#000000"))
    estilo.append(("BOX", (2, 0), (-1, 3), _GROSOR_GRUESO, "#000000"))
    idx = 2
    for _dia in dias:
        estilo.append(("BOX", (idx, 0), (idx + n_unidades - 1, 0), _GROSOR_GRUESO, "#000000"))
        idx += n_unidades
    idx = 2
    for _dia in dias:
        idx += n_unidades
        col_divisoria = idx - 1
        if col_divisoria < n_cols_datos + 1:
            estilo.append(("LINEAFTER", (col_divisoria, 0), (col_divisoria, ultima_fila), _GROSOR_GRUESO, "#000000"))
    for limite in limites_grupo:
        estilo.append(("LINEBELOW", (0, limite), (-1, limite), _GROSOR_GRUESO, "#000000"))
    for ini, fin in zip(inicios_grupo, limites_grupo + [ultima_fila]):
        estilo.append(("BOX", (0, ini), (1, fin), _GROSOR_GRUESO, "#000000"))
    estilo.append(("BOX", (0, 0), (-1, ultima_fila), _GROSOR_GRUESO, "#000000"))

    tabla.setStyle(TableStyle(estilo))
    return tabla


def _tabla_grilla_edificio_girada(
    conn: sqlite3.Connection, unidades: list[sqlite3.Row], grilla: dict, horas: list[int], ancho: float,
    anonimizar_unidad: bool = False,
) -> Table:
    """Misma grilla que `_tabla_grilla_edificio` pero con los ejes
    invertidos: Día + Unidad (piso/letra) pasan a ser filas (a la
    izquierda) y Tipo de bloque/Horario pasan a ser columnas (arriba). Se
    usa cuando un edificio tiene más unidades que
    `Configuracion.UmbralGiroGrilla` — la grilla "derecha" se volvería
    demasiado ancha, mientras que este documento ya es de página única
    continua (crece en alto sin límite), así que girarla la mantiene
    dentro del ancho de la página. Mismos colores, líneas gruesas
    estructurales y fuentes auto-ajustables que la versión sin girar."""
    dias = DIAS_GRILLA_DEFAULT
    tipo_por_hora = _tipo_bloque_por_hora(conn, horas)
    n_unidades = len(unidades)
    n_horas = max(len(horas), 1)

    ancho_dia, ancho_piso, ancho_letra = ancho * 0.10, ancho * 0.05, ancho * 0.05
    ancho_restante = ancho - ancho_dia - ancho_piso - ancho_letra
    ancho_col_hora = ancho_restante / n_horas

    def _partes_etiqueta(indice: int, u: sqlite3.Row) -> tuple[str, str]:
        if anonimizar_unidad:
            return str(indice + 1), ""
        return _partir_etiqueta_unidad(u["Departamento"])

    partes = [_partes_etiqueta(i, u) for i, u in enumerate(unidades)]
    textos_etiqueta = [p for par in partes for p in par if p]
    # Anonimizado: columnas 1-2 fusionadas en "Unidad", así que el número
    # dispone de todo el ancho combinado (no solo el de la más angosta).
    ancho_etiqueta_col = (ancho_piso + ancho_letra - 2) if anonimizar_unidad else min(ancho_piso, ancho_letra) - 2
    tamano_etiqueta = _tamano_que_entra(textos_etiqueta, ancho_etiqueta_col, fuente=FUENTE)
    style_etiqueta = estilo_texto(tamano_etiqueta, negrita=False, alignment=TA_CENTER, textColor=colors.white)
    diametro_dos_tonos = min(ancho_col_hora - 2, _DIAMETRO_DOS_TONOS_MAX)

    # El contenido de una celda combinada (SPAN) es el de su celda ancla —
    # la de arriba/izquierda. "Día"/"Piso"/"Depto." combinan las filas 0 y
    # 1 con ancla en la fila 0, así que van ahí (no en la fila 1).
    # Anonimizado: no hay piso/letra real que mostrar por separado, así que
    # las columnas 1 y 2 se fusionan en una sola "Unidad" (encabezado y, más
    # abajo, cada número de unidad centrado en el ancho combinado).
    fila_tipo: list = ["Día", "Unidad" if anonimizar_unidad else "Piso", "Depto."] + [""] * n_horas
    fila_horario: list = ["", "", ""] + [hora_fmt(h) for h in horas]
    filas = [fila_tipo, fila_horario]

    limites_grupo_col: list[int] = []  # última columna de cada grupo rígido/flexible
    inicios_grupo_col: list[int] = []
    tipo_anterior, inicio_grupo = None, None
    for col_idx, h in enumerate(horas, start=3):
        tipo = tipo_por_hora[h]
        if tipo != tipo_anterior:
            if tipo_anterior is not None:
                limites_grupo_col.append(col_idx - 1)
                inicios_grupo_col.append(inicio_grupo)
            inicio_grupo, tipo_anterior = col_idx, tipo
        filas[0][col_idx] = tipo
    limites_grupo_col.append(n_horas + 2)
    inicios_grupo_col.append(inicio_grupo)

    fondos = []
    for dia in dias:
        for par, u in zip(partes, unidades):
            fila_idx = len(filas)
            fila = [dia.upper(), Paragraph(par[0], style_etiqueta), Paragraph(par[1], style_etiqueta)]
            for h in horas:
                color = grilla.get((u["IdUnidad"], dia, h), "rojo")
                fila.append(_CeldaDosTonos(diametro_dos_tonos) if color == "naranja" else "")
                fondos.append((color, fila_idx, len(fila) - 1))
            filas.append(fila)

    ultima_fila = len(filas) - 1
    col_widths = [ancho_dia, ancho_piso, ancho_letra] + [ancho_col_hora] * n_horas
    tabla = Table(filas, colWidths=col_widths, repeatRows=2)

    estilo = [
        ("FONTNAME", (0, 0), (-1, -1), FUENTE_NEGRITA),
        ("FONTSIZE", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.3, "#999999"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 1),
        ("RIGHTPADDING", (0, 0), (-1, -1), 1),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("BACKGROUND", (0, 0), (2, 1), COLOR_NIVEL_1),
        ("TEXTCOLOR", (0, 0), (2, 1), "#FFFFFF"),
        ("BACKGROUND", (3, 0), (-1, 1), COLOR_NIVEL_1),
        ("TEXTCOLOR", (3, 0), (-1, 1), "#FFFFFF"),
        ("BACKGROUND", (0, 2), (0, ultima_fila), COLOR_NIVEL_1),
        ("TEXTCOLOR", (0, 2), (0, ultima_fila), "#FFFFFF"),
        ("FONTSIZE", (0, 2), (0, ultima_fila), 8),  # con varias filas de alto de sobra, entra más grande
        ("BACKGROUND", (1, 2), (2, ultima_fila), COLOR_NIVEL_1),
        ("TEXTCOLOR", (1, 2), (2, ultima_fila), "#FFFFFF"),
        # El divisor entre la columna de piso y la de letra se pinta del
        # mismo azul que el fondo para que quede invisible, igual que en
        # la grilla sin girar.
        ("LINEAFTER", (1, 2), (1, ultima_fila), 1.2, COLOR_NIVEL_1),
        # "Día"/"Piso"/"Depto." combinan las 2 filas de encabezado. Anonimizado:
        # "Piso" y "Depto." además se combinan ENTRE SÍ en una sola "Unidad"
        # (reportlab no dibuja líneas internas dentro de un SPAN, así que el
        # LINEAFTER de más abajo entre columna 1 y 2 queda automáticamente
        # suprimido sin necesidad de condicionarlo aparte).
        ("SPAN", (0, 0), (0, 1)),
        ("SPAN", (1, 0), (2, 1) if anonimizar_unidad else (1, 1)),
    ] + ([] if anonimizar_unidad else [("SPAN", (2, 0), (2, 1))]) + [
        # Título de cada columna de encabezado separado con línea gruesa.
        ("LINEAFTER", (0, 0), (0, 1), _GROSOR_GRUESO, "#000000"),
        ("LINEAFTER", (1, 0), (1, 1), _GROSOR_GRUESO, "#000000"),
    ]
    for ini, fin in zip(inicios_grupo_col, limites_grupo_col):
        estilo.append(("SPAN", (ini, 0), (fin, 0)))
    idx = 2
    for _dia in dias:
        estilo.append(("SPAN", (0, idx), (0, idx + n_unidades - 1)))
        idx += n_unidades
    if anonimizar_unidad:
        # Mismo criterio que el encabezado: el número de unidad va centrado
        # en el ancho combinado de las columnas 1-2, no pegado a la izquierda.
        for fila_idx in range(2, len(filas)):
            estilo.append(("SPAN", (1, fila_idx), (2, fila_idx)))
    for color, fila, col in fondos:
        estilo.append(("BACKGROUND", (col, fila), (col, fila), _COLOR_CELDA[color]))

    # Mismas líneas estructurales gruesas que la versión sin girar, con
    # filas y columnas intercambiadas: marco de Día/Piso/Depto., marco de
    # Tipo Bloque/Horario, un divisor por cada día, un divisor entre cada
    # grupo rígido/flexible, una caja por cada grupo con su horario, y un
    # marco grueso alrededor de toda la grilla.
    estilo.append(("BOX", (0, 0), (2, 1), _GROSOR_GRUESO, "#000000"))
    estilo.append(("BOX", (3, 0), (-1, 1), _GROSOR_GRUESO, "#000000"))
    idx = 2
    for _dia in dias:
        # Dos cajas separadas por día: una solo para la palabra del día
        # (columna 0) y otra que engloba piso+depto. de todas sus unidades
        # (columnas 1-2) — no las columnas de horario, esas solo quedan
        # separadas por el divisor horizontal entre días de más abajo.
        estilo.append(("BOX", (0, idx), (0, idx + n_unidades - 1), _GROSOR_GRUESO, "#000000"))
        estilo.append(("BOX", (1, idx), (2, idx + n_unidades - 1), _GROSOR_GRUESO, "#000000"))
        idx += n_unidades
        if idx <= ultima_fila + 1:
            estilo.append(("LINEBELOW", (0, idx - 1), (-1, idx - 1), _GROSOR_GRUESO, "#000000"))
    for ini, fin in zip(inicios_grupo_col, limites_grupo_col):
        estilo.append(("BOX", (ini, 0), (fin, 1), _GROSOR_GRUESO, "#000000"))
        if fin < n_horas + 2:
            estilo.append(("LINEAFTER", (fin, 0), (fin, ultima_fila), _GROSOR_GRUESO, "#000000"))
    estilo.append(("BOX", (0, 0), (-1, ultima_fila), _GROSOR_GRUESO, "#000000"))

    tabla.setStyle(TableStyle(estilo))
    return tabla


def _umbral_giro_grilla(conn: sqlite3.Connection) -> int:
    cfg = conn.execute("SELECT UmbralGiroGrilla FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
    return int(cfg["UmbralGiroGrilla"]) if cfg and cfg["UmbralGiroGrilla"] is not None else 8


def altura_estimada_grilla(conn: sqlite3.Connection, ids_edificio: list[int] | None = None) -> float:
    """Estimación de alto ocupado por la sección de disponibilidad
    (grilla + leyenda + notas) de cada edificio relevante. En vez de
    adivinar un alto por fila (que se desactualiza solo con tocar
    padding/fuente), arma la tabla real de cada edificio — girada o no,
    según corresponda — y le pregunta a reportlab (`Table.wrap`) el alto
    que efectivamente va a ocupar."""
    cfg = conn.execute(
        "SELECT HoraInicioGrilla, HoraFinGrilla FROM Configuracion WHERE IdConfiguracion = 1"
    ).fetchone()
    hora_ini = int(cfg["HoraInicioGrilla"]) if cfg else 8
    hora_fin = int(cfg["HoraFinGrilla"]) if cfg else 22
    horas = list(range(hora_ini, hora_fin)) or [hora_ini]
    umbral = _umbral_giro_grilla(conn)

    unidades = _unidades_por_edificio(conn, ids_edificio)
    por_edificio: dict[int, list[sqlite3.Row]] = {}
    for u in unidades:
        por_edificio.setdefault(u["IdEdificio"], []).append(u)
    grupos = list(por_edificio.values()) or [[{"IdUnidad": 0, "Departamento": "X"}]]

    ancho_ref = A4[0] - 2 * MARGEN  # mismo ancho útil que usa crear_documento
    total = 0.0
    for unidades_ed in grupos:
        constructor = _tabla_grilla_edificio_girada if len(unidades_ed) > umbral else _tabla_grilla_edificio
        tabla = constructor(conn, unidades_ed, {}, horas, ancho_ref)
        _, alto = tabla.wrap(ancho_ref, 1000 * cm)
        total += alto + 5 * cm  # + título del edificio, leyenda, notas y espaciadores
    return total


def secciones_disponibilidad(
    conn: sqlite3.Connection, anio: int, mes: int, ancho: float, fecha_titulo: str,
    ids_edificio: list[int] | None = None, anonimizar_unidad: bool = False,
    mostrar_titulo: bool = True, mostrar_encabezado_edificio: bool = True,
) -> list:
    """Nivel 2 "Disponibilidad de consultorios al {fecha_titulo}" seguido,
    por cada edificio relevante, de un nivel 3 con su grilla completa +
    leyenda + notas de horarios rígidos/flexibles (sección 4.2).

    `mostrar_titulo`/`mostrar_encabezado_edificio` en False dejan afuera el
    título compartido y/o el "Edificio {Nombre}" nivel 3 de cada bloque —
    el PDF de Propuesta arma su propio título (nivel 1, o nivel 2 por
    edificio cuando hay más de uno) y no necesita este duplicado."""
    cfg = conn.execute(
        "SELECT HoraInicioGrilla, HoraFinGrilla FROM Configuracion WHERE IdConfiguracion = 1"
    ).fetchone()
    hora_ini = int(cfg["HoraInicioGrilla"]) if cfg else 8
    hora_fin = int(cfg["HoraFinGrilla"]) if cfg else 22
    umbral_giro = _umbral_giro_grilla(conn)
    horas = list(range(hora_ini, hora_fin))
    dias = DIAS_GRILLA_DEFAULT

    grilla = calcular_grilla(conn, anio, mes, hora_ini, hora_fin, dias)
    unidades = _unidades_por_edificio(conn, ids_edificio)

    por_edificio: dict[int, list[sqlite3.Row]] = {}
    nombres: dict[int, str] = {}
    for u in unidades:
        por_edificio.setdefault(u["IdEdificio"], []).append(u)
        nombres[u["IdEdificio"]] = u["NombreEdificio"]
    # Anonimizado (Propuesta): orden por número de unidad ascendente, no
    # por piso — la etiqueta ya no muestra el piso real, así que ordenar
    # por él saltearía sin ningún criterio visible ("Unidad 2" antes que
    # "Unidad 1"). Sin anonimizar: piso ascendente y letra alfabética,
    # como en el resto del sistema.
    for id_edificio in por_edificio:
        if anonimizar_unidad:
            por_edificio[id_edificio].sort(key=lambda u: u["IdUnidad"])
        else:
            por_edificio[id_edificio].sort(key=lambda u: clave_orden_unidad(u["Departamento"]))

    style_nota = estilo_texto(7, negrita=True, italica=True)

    story = []
    if mostrar_titulo:
        story.append(encabezado(2, f"Disponibilidad de consultorios al {fecha_titulo}", ancho))
        story.append(Spacer(1, 6))
    for id_edificio, unidades_ed in por_edificio.items():
        constructor_tabla = _tabla_grilla_edificio_girada if len(unidades_ed) > umbral_giro else _tabla_grilla_edificio
        bloque = []
        if mostrar_encabezado_edificio:
            bloque.append(encabezado(3, f"Edificio {nombres[id_edificio]}", ancho))
            bloque.append(Spacer(1, 6))
        bloque.extend([
            constructor_tabla(conn, unidades_ed, grilla, horas, ancho, anonimizar_unidad),
            Spacer(1, 4),
            _tabla_leyenda(ancho),
            Paragraph(
                "Horarios rígidos: son bloques de horas consecutivas que se deben reservar sí o sí todas "
                "juntas, estos bloques no se fraccionan.", style_nota,
            ),
            Paragraph(
                "Horarios flexibles: las horas comprendidas dentro de estos bloques se pueden reservar sin "
                "restricción y sin mínimo alguno.", style_nota,
            ),
            Spacer(1, 8),
        ])
        story.append(KeepTogether(bloque))
    return story


def _tabla_leyenda(ancho: float) -> Table:
    filas = [
        [" ", "Hay al menos dos consultorios disponibles", _CeldaDosTonos(8), "Solo un consultorio disponible sin ventana"],
        [" ", "Solo un consultorio disponible con ventana", " ", "Sin consultorios disponibles"],
    ]
    tabla = Table(filas, colWidths=[ancho * 0.04, ancho * 0.46, ancho * 0.04, ancho * 0.46])
    tabla.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("BACKGROUND", (0, 0), (0, 0), COLOR_VERDE),
        ("BACKGROUND", (0, 1), (0, 1), COLOR_AMARILLO),
        ("BACKGROUND", (2, 0), (2, 0), COLOR_AMARILLO),
        ("BACKGROUND", (2, 1), (2, 1), COLOR_ROJO),
        ("ALIGN", (2, 0), (2, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (0, 0), _GROSOR_GRUESO, "#000000"),
        ("BOX", (0, 1), (0, 1), _GROSOR_GRUESO, "#000000"),
        ("BOX", (2, 0), (2, 0), _GROSOR_GRUESO, "#000000"),
        ("BOX", (2, 1), (2, 1), _GROSOR_GRUESO, "#000000"),
    ]))
    return tabla
