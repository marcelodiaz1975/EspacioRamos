"""Ventana principal: navegación lateral + panel de contenido apilado.

Cada pantalla se registra como (nombre, categoría, fábrica) — la fábrica
recibe la conexión abierta y devuelve el QWidget de esa sección. Las
pantallas se instancian de una sola vez (no al hacer clic) para que
conserven su estado entre visitas dentro de la misma sesión."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.gui.estilos import hoja_estilos, paleta
from app.gui.recursos import RUTA_ICONO
from app.gui.widgets.calculadora import Calculadora
from app.negocio.avance_mes import puede_avanzarse_mes
from app.negocio.dias import periodo_actual
from app.negocio.plantillas_texto import resolver_plantilla
from app.negocio.seguridad import nivel_alcanza
from app.version import NOMBRE_Y_VERSION


def _pantalla_inicial() -> QWidget:
    """Pedido de la clienta: al abrir el sistema no se ve ninguna
    pantalla todavía (ni siquiera "Panel de control", que antes se abría
    sola) — solo el ícono del programa centrado, hasta el primer click
    en cualquier solapa del menú. Reemplaza la regla anterior ("al abrir
    el programa, siempre arranca en Panel de control")."""
    contenedor = QWidget()
    layout = QVBoxLayout(contenedor)
    etiqueta = QLabel()
    etiqueta.setAlignment(Qt.AlignmentFlag.AlignCenter)
    pixmap = QPixmap(str(RUTA_ICONO))
    if not pixmap.isNull():
        etiqueta.setPixmap(
            pixmap.scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        )
    layout.addWidget(etiqueta)
    return contenedor


@dataclass
class Seccion:
    nombre: str
    fabrica: Callable[[sqlite3.Connection], QWidget]
    categoria: str = "General"
    ayuda: str = ""


_INDICE_PILA = Qt.ItemDataRole.UserRole
_CATEGORIA_SEPARADOR = Qt.ItemDataRole.UserRole + 1


class VentanaPrincipal(QMainWindow):
    def __init__(self, conn: sqlite3.Connection, secciones: list[Seccion], *, id_nivel_usuario: int | None = None):
        super().__init__()
        self.conn = conn
        # Seguridad (ver CLAUDE.md): `id_nivel_usuario` es el nivel del
        # usuario logueado (gui_main.main arma el login antes de esta
        # ventana). `None` — el default, el que usan todos los tests que
        # construyen la ventana directo sin pasar por el login — no
        # filtra nada, para no tener que loguearse en cada test de
        # pantalla que no tiene nada que ver con Seguridad.
        if id_nivel_usuario is None:
            secciones_visibles = secciones
        else:
            secciones_visibles = [s for s in secciones if nivel_alcanza(conn, id_nivel_usuario, s.nombre)]
        self.setWindowTitle(NOMBRE_Y_VERSION)
        self.resize(1200, 800)
        self._aplicar_tema()

        self._navegacion = QListWidget()
        self._navegacion.setObjectName("navegacion")
        self._navegacion.setFixedWidth(240)
        self._pila = QStackedWidget()
        self._pantalla_inicial = _pantalla_inicial()
        self._pila.addWidget(self._pantalla_inicial)

        # Punto 20 (SistemaDF v0.11.2026.10): las dos categorías del menú
        # arrancan COLAPSADAS — clickear el separador de una categoría la
        # despliega/colapsa, acordeón. "Panel de control" tenía antes una
        # excepción (quedaba siempre visible sin importar el estado de su
        # categoría) porque el sistema arrancaba abriéndola sola; corrección
        # de la clienta tras sacar esa regla (ver `_pantalla_inicial`): ya
        # no hace falta — "Panel de control" se colapsa/expande con el
        # resto de los ítems de su categoría, como cualquier otro.
        self._categorias_expandidas: dict[str, bool] = {}
        self._separadores_por_categoria: dict[str, QListWidgetItem] = {}
        self._items_por_categoria: dict[str, list[QListWidgetItem]] = {}
        # Índice en `self._pila` -> Seccion. NO se puede asumir que
        # coincide con la posición de la Seccion en `self._secciones`
        # (`_pantalla_inicial` ocupa el índice 0 de la pila sin tener
        # Seccion propia, así que todo lo demás queda corrido).
        self._seccion_por_indice_pila: dict[int, Seccion] = {}

        categoria_actual = None
        for seccion in secciones_visibles:
            if seccion.categoria != categoria_actual:
                separador = QListWidgetItem()
                separador.setFlags(Qt.ItemFlag.ItemIsEnabled)
                # Pedido de la clienta: negrita en la etiqueta de categoría.
                # `::item:disabled` de `estilos.py` no le pega acá — el
                # ítem queda ENABLED (solo se le sacó ItemIsSelectable), así
                # que ese selector de QSS nunca matchea; se fija la fuente
                # directo sobre el ítem en vez de depender de esa regla.
                fuente_negrita = separador.font()
                fuente_negrita.setBold(True)
                separador.setFont(fuente_negrita)
                separador.setData(_CATEGORIA_SEPARADOR, seccion.categoria)
                self._navegacion.addItem(separador)
                self._separadores_por_categoria[seccion.categoria] = separador
                self._categorias_expandidas.setdefault(seccion.categoria, False)
                self._items_por_categoria.setdefault(seccion.categoria, [])
                categoria_actual = seccion.categoria

            indice_pila = self._pila.count()
            widget = seccion.fabrica(conn)
            self._pila.addWidget(widget)
            self._seccion_por_indice_pila[indice_pila] = seccion

            item = QListWidgetItem(seccion.nombre)
            item.setData(_INDICE_PILA, indice_pila)
            self._navegacion.addItem(item)
            self._items_por_categoria[seccion.categoria].append(item)

        for categoria in self._categorias_expandidas:
            self._aplicar_colapso(categoria)

        self._navegacion.itemClicked.connect(self._al_click_item_navegacion)

        self._barra_fecha_ficticia = QLabel()
        self._barra_fecha_ficticia.setObjectName("barraFechaFicticia")
        self._barra_fecha_ficticia.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._barra_fecha_ficticia.hide()

        self._badge_periodo = QLabel()
        self._badge_periodo.setObjectName("badgePeriodo")
        self.statusBar().addPermanentWidget(self._badge_periodo)
        self._actualizar_badge_periodo()

        # Pedido general de la clienta: "en la línea donde se ve el
        # período... al borde de la izquierda" — `addWidget` (a diferencia
        # de `addPermanentWidget`, usado arriba para el período) ubica en
        # el área IZQUIERDA de la barra de estado, de siempre en Qt.
        #
        # Pedido explícito de la clienta (hilo "saldo actual"/atajos de
        # teclado): atajos F1-F12 completos como salto directo a una
        # solapa puntual del sistema (ver `ir_a_solapa`), con F5
        # ("Refrescar") en el medio ocupando el lugar del viejo F3
        # ("Reiniciar solapa" — el nombre de tecla cambió, el método
        # `_reiniciar_solapa_activa` sigue siendo el mismo). El orden es
        # el que pidió la clienta, no alfabético ni por categoría de menú.
        self._etiqueta_funciones = QLabel(
            "F1 – Ayuda / F2 – Calculadora / F3 – Regulares / F4 – Aisladas / F5 – Refrescar / "
            "F6 – Grilla / F7 – Mensajería / F8 – Predefinidos / F9 – Oferta / F10 – Profesionales / "
            "F11 – Llaves / F12 – Placas"
        )
        self.statusBar().addWidget(self._etiqueta_funciones)

        self._calculadora: Calculadora | None = None
        self._atajo_calculadora = QShortcut(Qt.Key.Key_F2, self)
        self._atajo_calculadora.activated.connect(self._abrir_calculadora)

        self._atajo_regulares = QShortcut(Qt.Key.Key_F3, self)
        self._atajo_regulares.activated.connect(lambda: self.ir_a_solapa("Reservas", "Reservas regulares"))
        self._atajo_aisladas = QShortcut(Qt.Key.Key_F4, self)
        self._atajo_aisladas.activated.connect(lambda: self.ir_a_solapa("Reservas", "Reservas aisladas"))
        self._atajo_reiniciar = QShortcut(Qt.Key.Key_F5, self)
        self._atajo_reiniciar.activated.connect(self._reiniciar_solapa_activa)
        self._atajo_grilla = QShortcut(Qt.Key.Key_F6, self)
        self._atajo_grilla.activated.connect(lambda: self.ir_a_solapa("Grilla y mensajería", "Grilla semanal"))
        self._atajo_mensajeria = QShortcut(Qt.Key.Key_F7, self)
        self._atajo_mensajeria.activated.connect(
            lambda: self.ir_a_solapa("Grilla y mensajería", "Centro de mensajería")
        )
        self._atajo_predefinidos = QShortcut(Qt.Key.Key_F8, self)
        self._atajo_predefinidos.activated.connect(
            lambda: self.ir_a_solapa("Grilla y mensajería", "Mensajes predefinidos")
        )
        self._atajo_oferta = QShortcut(Qt.Key.Key_F9, self)
        self._atajo_oferta.activated.connect(lambda: self.ir_a_solapa("Disponibilidad", "Oferta de consultorios"))
        self._atajo_profesionales = QShortcut(Qt.Key.Key_F10, self)
        self._atajo_profesionales.activated.connect(
            lambda: self.ir_a_solapa("Profesionales", "Listado de profesionales")
        )
        self._atajo_llaves = QShortcut(Qt.Key.Key_F11, self)
        self._atajo_llaves.activated.connect(
            lambda: self.ir_a_solapa("Llaves y otros conceptos", "Movimientos y tenencias de llaves")
        )
        self._atajo_placas = QShortcut(Qt.Key.Key_F12, self)
        self._atajo_placas.activated.connect(
            lambda: self.ir_a_solapa("Placas para timbres", "Búsqueda y asignación de placas")
        )

        self._navegacion.currentRowChanged.connect(self._cambiar_seccion)
        # Pedido de la clienta: al abrir, ninguna fila queda seleccionada
        # todavía (ni "Panel de control", que antes se abría sola) — se ve
        # el ícono centrado (`self._pantalla_inicial`, ya puesto como
        # página actual de `self._pila` más arriba) hasta el primer click
        # en cualquier solapa, que recién ahí dispara `_cambiar_seccion`
        # vía `currentRowChanged`. Reemplaza la regla anterior.
        self._actualizar_barra_fecha_ficticia()

        fila_principal = QWidget()
        layout_fila = QHBoxLayout(fila_principal)
        layout_fila.setContentsMargins(0, 0, 0, 0)
        layout_fila.setSpacing(0)
        layout_fila.addWidget(self._navegacion)
        layout_fila.addWidget(self._pila, stretch=1)

        contenedor = QWidget()
        layout = QVBoxLayout(contenedor)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._barra_fecha_ficticia)
        layout.addWidget(fila_principal, stretch=1)
        self.setCentralWidget(contenedor)

        self._atajo_ayuda = QShortcut(Qt.Key.Key_F1, self)
        self._atajo_ayuda.activated.connect(self._mostrar_ayuda)

    def _texto_separador(self, categoria: str, expandida: bool) -> str:
        """Pedido de la clienta: sin los guiones decorativos alrededor del
        nombre de categoría — solo la flecha de expandir/colapsar y el
        nombre en mayúscula."""
        flecha = "▾" if expandida else "▸"
        return f"{flecha} {categoria.upper()}"

    def _aplicar_colapso(self, categoria: str) -> None:
        expandida = self._categorias_expandidas[categoria]
        self._separadores_por_categoria[categoria].setText(self._texto_separador(categoria, expandida))
        for item in self._items_por_categoria[categoria]:
            item.setHidden(not expandida)

    def _al_click_item_navegacion(self, item: QListWidgetItem) -> None:
        """Punto 20: clickear el separador de una categoría la despliega/
        colapsa — un ítem de pantalla normal (sin esta marca) no hace
        nada acá, la selección ya la maneja `currentRowChanged`."""
        categoria = item.data(_CATEGORIA_SEPARADOR)
        if categoria is None:
            return
        self._categorias_expandidas[categoria] = not self._categorias_expandidas[categoria]
        self._aplicar_colapso(categoria)

    def _abrir_calculadora(self) -> None:
        """F2 alterna la calculadora: la pone en pantalla la primera vez,
        la saca si se vuelve a apretar mientras ya está abierta (pedido
        de la clienta) — una sola instancia por ventana, y `_calculadora`
        queda en `None` otra vez al cerrarse (señal `destroyed`, se
        dispara tanto por este toggle como por la cruz o Escape) para
        que la próxima F2 abra una nueva."""
        if self._calculadora is None:
            self._calculadora = Calculadora(self)
            self._calculadora.destroyed.connect(self._al_cerrar_calculadora)
            self._calculadora.show()
        else:
            self._calculadora.close()

    def _al_cerrar_calculadora(self) -> None:
        self._calculadora = None

    def _panel_mas_interno(self) -> QWidget | None:
        """Baja por la cadena de `QTabWidget` anidados hasta el panel de
        verdad que se está viendo en este momento — una pantalla compuesta
        (ej. "Archivos y listas") es un `QTabWidget` cuyo contenido de cada
        pestaña puede a su vez ser OTRO formulario con sus propias
        solapas. `visto` evita un loop infinito si alguna vez un
        `QTabWidget` quedara anidado dentro de sí mismo (no debería pasar,
        es una guarda defensiva nomás)."""
        widget = self._pila.currentWidget()
        visto: set[int] = set()
        while isinstance(widget, QTabWidget) and id(widget) not in visto:
            visto.add(id(widget))
            siguiente = widget.currentWidget()
            if siguiente is None:
                break
            widget = siguiente
        return widget

    def _reiniciar_solapa_activa(self) -> None:
        """F3: "reinicia la solapa, la resetea, como recién se entrara en
        ella" — mismo método (`reiniciar`) que cada panel ya implementa
        para el reseteo automático al cambiar de pestaña (ver #1.4); los
        paneles que todavía no lo tienen simplemente no hacen nada con F3,
        en vez de romper."""
        panel = self._panel_mas_interno()
        if panel is not None and hasattr(panel, "reiniciar"):
            panel.reiniciar()

    def ir_a_seccion(self, nombre: str) -> QWidget | None:
        """Salta a la Seccion de nombre `nombre` (la selecciona en el menú
        lateral, como si el operador hubiera clickeado ahí) y devuelve su
        widget — para que una pantalla pueda mandar a otra (#22: "Confirmar
        reserva" de Lista de espera -> Reservas). Primera vez que hace
        falta este tipo de salto en el sistema; se pensó como un método
        chico y reusable en vez de algo hecho a medida para ese botón
        puntual, para que cualquier pantalla futura con la misma necesidad
        lo pueda reusar. None si no se encuentra `nombre` (mal escrito, o
        esa Seccion no está visible para el nivel del usuario logueado —
        ver Seguridad)."""
        for fila in range(self._navegacion.count()):
            item = self._navegacion.item(fila)
            indice_pila = item.data(_INDICE_PILA)
            if indice_pila is None:
                continue
            if self._seccion_por_indice_pila[indice_pila].nombre == nombre:
                categoria = self._seccion_por_indice_pila[indice_pila].categoria
                if not self._categorias_expandidas.get(categoria, True):
                    self._categorias_expandidas[categoria] = True
                    self._aplicar_colapso(categoria)
                self._navegacion.setCurrentRow(fila)
                return self._pila.widget(indice_pila)
        return None

    def ir_a_solapa(self, nombre_seccion: str, texto_solapa: str) -> QWidget | None:
        """Atajo de teclado F3-F12 (ver `_etiqueta_funciones`): salta a la
        Seccion `nombre_seccion` (vía `ir_a_seccion`) y, si es una pantalla
        compuesta con solapas propias (atributo `pestanas`, el `QTabWidget`
        que arma cada pantalla así — Reservas, Grilla y mensajería,
        Disponibilidad, Profesionales, Llaves y otros conceptos, Placas
        para timbres), se para además en la solapa de texto `texto_solapa`
        dentro de ella. Si la Seccion no tiene solapas propias (o no se
        encuentra `texto_solapa` entre ellas), se queda solo con el salto
        de `ir_a_seccion`, sin romper. `findChild` alcanza aunque el
        `QTabWidget` esté dentro de un layout intermedio, no directamente
        como hijo."""
        widget = self.ir_a_seccion(nombre_seccion)
        if widget is None:
            return None
        pestanas = widget.findChild(QTabWidget)
        if pestanas is None:
            return widget
        for indice in range(pestanas.count()):
            if pestanas.tabText(indice) == texto_solapa:
                pestanas.setCurrentIndex(indice)
                return pestanas.widget(indice)
        return widget

    def _mostrar_ayuda(self) -> None:
        """Ayuda contextual (Etapa 11): F1 muestra el texto de ayuda de
        la pantalla actualmente visible, tomado de Seccion.ayuda — salvo
        que se haya personalizado desde "Textos del sistema" (pedido de
        la clienta, ver `app.negocio.plantillas_texto`)."""
        indice_pila = self._pila.currentIndex()
        seccion = self._seccion_por_indice_pila.get(indice_pila)
        if seccion is None:
            return
        default = seccion.ayuda or "Esta pantalla todavía no tiene ayuda contextual cargada."
        texto = resolver_plantilla(self.conn, f"ayuda:{seccion.nombre}", default)
        QMessageBox.information(self, f"Ayuda — {seccion.nombre}", texto)

    def _aplicar_tema(self) -> None:
        """Modo oscuro/claro (Configuracion.ModoOscuro, default claro): la
        hoja de estilos cubre los widgets con nombre propio (títulos,
        botón primario, etc.) y la QPalette a nivel QApplication cubre el
        resto (campos, tablas, checkboxes, diálogos) sin tener que
        escribir una regla por cada pantalla. Se revisa en cada cambio de
        sección, igual que la barra de fecha ficticia, para que el
        cambio hecho en Configuración general se vea sin reiniciar."""
        cfg = self.conn.execute("SELECT ModoOscuro FROM Configuracion WHERE IdConfiguracion = 1").fetchone()
        modo_oscuro = bool(cfg and cfg["ModoOscuro"])
        app = QApplication.instance()
        if app is not None:
            app.setPalette(paleta(modo_oscuro))
        self.setStyleSheet(hoja_estilos(modo_oscuro))

    def _actualizar_barra_fecha_ficticia(self) -> None:
        """Modo de fecha ficticia para testing (sección 2): barra bien
        visible mientras está activo, para no confundir datos de prueba
        con reales — se revisa en cada cambio de pantalla, ya que
        Configuración general puede activarlo/desactivarlo en cualquier
        momento durante la sesión.

        Fuera de ese modo, la misma barra (no se necesitan las dos a la
        vez: mientras la fecha ficticia está activa no corre el recorte
        de `fecha_actual` contra el período operativo) avisa si "Avanzar
        de mes" dejó al sistema parado un período por delante de la fecha
        real — pedido de la clienta ("no lo necesitaría, pero tampoco me
        molesta, agregalo por si acaso")."""
        cfg = self.conn.execute(
            "SELECT ModoFechaFicticia, FechaFicticia FROM Configuracion WHERE IdConfiguracion = 1"
        ).fetchone()
        if cfg and cfg["ModoFechaFicticia"] and cfg["FechaFicticia"]:
            self._barra_fecha_ficticia.setText(
                f"⚠ MODO FECHA FICTICIA ACTIVO — Hoy simulado: {cfg['FechaFicticia']} ⚠"
            )
            self._barra_fecha_ficticia.show()
        elif not puede_avanzarse_mes(self.conn):
            self._barra_fecha_ficticia.setText(
                f"⚠ AVANCE DE MES ADELANTADO — Período operativo: {self._periodo_legible()} "
                f"(fecha real de hoy: {date.today():%d-%m-%Y}) ⚠"
            )
            self._barra_fecha_ficticia.show()
        else:
            self._barra_fecha_ficticia.hide()

    def _actualizar_badge_periodo(self) -> None:
        """Miscelánea (ago-2026): el período en el que está posicionado el
        sistema tiene que estar siempre a la vista en cualquier pantalla —
        se revisa en cada cambio de sección, igual que la barra de fecha
        ficticia, para que un avance de mes se refleje sin reiniciar.

        Pedido de la clienta en el hilo de "saldo actual"/atajos de
        teclado: mismo azul que los encabezados de columna de las tablas
        (`COLOR_NIVEL_1_OSCURO`, ver `estilos.py#badgePeriodo`), negrita y
        mayúscula — `.upper()` en el texto porque QSS no soporta
        text-transform, mismo criterio que `tituloPantalla`."""
        self._badge_periodo.setText(f"Período {self._periodo_legible()}".upper())

    def _periodo_legible(self) -> str:
        anio, mes = periodo_actual(self.conn).split("-")
        return f"{mes}/{anio}"

    def _cambiar_seccion(self, fila: int) -> None:
        if fila < 0:
            return
        item = self._navegacion.item(fila)
        indice_pila = item.data(_INDICE_PILA)
        if indice_pila is None:
            return
        self._pila.setCurrentIndex(indice_pila)
        self._actualizar_barra_fecha_ficticia()
        self._actualizar_badge_periodo()
        self._aplicar_tema()
