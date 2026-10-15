"""Ventana principal: navegación lateral + panel de contenido apilado.

Cada pantalla se registra como (nombre, categoría, fábrica) — la fábrica
recibe la conexión abierta y devuelve el QWidget de esa sección. Las
pantallas se instancian de una sola vez (no al hacer clic) para que
conserven su estado entre visitas dentro de la misma sesión."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QShortcut
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
from app.gui.widgets.calculadora import Calculadora
from app.negocio.dias import periodo_actual
from app.negocio.plantillas_texto import resolver_plantilla
from app.negocio.seguridad import nivel_alcanza
from app.version import NOMBRE_Y_VERSION


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
        self._secciones = secciones_visibles
        self.setWindowTitle(NOMBRE_Y_VERSION)
        self.resize(1200, 800)
        self._aplicar_tema()

        self._navegacion = QListWidget()
        self._navegacion.setObjectName("navegacion")
        self._navegacion.setFixedWidth(240)
        self._pila = QStackedWidget()

        # Punto 20 (SistemaDF v0.11.2026.10): las dos categorías del menú
        # arrancan COLAPSADAS — clickear el separador de una categoría la
        # despliega/colapsa, acordeón. "Panel de control" queda SIEMPRE
        # visible sin importar el estado de su categoría (se excluye de
        # `_items_por_categoria`, la lista que `_aplicar_colapso` oculta/
        # muestra) — es la pantalla de entrada de siempre, no tiene
        # sentido que quede escondida detrás de un clic.
        self._categorias_expandidas: dict[str, bool] = {}
        self._separadores_por_categoria: dict[str, QListWidgetItem] = {}
        self._items_por_categoria: dict[str, list[QListWidgetItem]] = {}

        categoria_actual = None
        primer_item_seleccionable = None
        fila_panel_control = None
        for seccion in secciones_visibles:
            if seccion.categoria != categoria_actual:
                separador = QListWidgetItem()
                separador.setFlags(Qt.ItemFlag.ItemIsEnabled)
                separador.setData(_CATEGORIA_SEPARADOR, seccion.categoria)
                self._navegacion.addItem(separador)
                self._separadores_por_categoria[seccion.categoria] = separador
                self._categorias_expandidas.setdefault(seccion.categoria, False)
                self._items_por_categoria.setdefault(seccion.categoria, [])
                categoria_actual = seccion.categoria

            indice_pila = self._pila.count()
            widget = seccion.fabrica(conn)
            self._pila.addWidget(widget)

            item = QListWidgetItem(seccion.nombre)
            item.setData(_INDICE_PILA, indice_pila)
            self._navegacion.addItem(item)
            if seccion.nombre != "Panel de control":
                self._items_por_categoria[seccion.categoria].append(item)
            if primer_item_seleccionable is None:
                primer_item_seleccionable = self._navegacion.count() - 1
            if seccion.nombre == "Panel de control":
                fila_panel_control = self._navegacion.count() - 1

        for categoria in self._categorias_expandidas:
            self._aplicar_colapso(categoria)

        self._navegacion.itemClicked.connect(self._al_click_item_navegacion)

        # Pedido general de la clienta: al abrir el programa, siempre
        # arranca en "Panel de control" — por NOMBRE, no por posición, para
        # que un reordenamiento futuro del menú (ver `gui_main.
        # construir_secciones`) no corra accidentalmente cuál es la
        # pantalla inicial. Sin esa Seccion en la lista (algún nivel de
        # usuario sin acceso a ella), cae al primer ítem seleccionable de
        # siempre.
        if fila_panel_control is not None:
            primer_item_seleccionable = fila_panel_control

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
        self._etiqueta_funciones = QLabel("F1 – Ayuda / F2 – Calculadora / F3 – Reiniciar solapa")
        self.statusBar().addWidget(self._etiqueta_funciones)

        self._calculadora: Calculadora | None = None
        self._atajo_calculadora = QShortcut(Qt.Key.Key_F2, self)
        self._atajo_calculadora.activated.connect(self._abrir_calculadora)
        self._atajo_reiniciar = QShortcut(Qt.Key.Key_F3, self)
        self._atajo_reiniciar.activated.connect(self._reiniciar_solapa_activa)

        self._navegacion.currentRowChanged.connect(self._cambiar_seccion)
        if primer_item_seleccionable is not None:
            self._navegacion.setCurrentRow(primer_item_seleccionable)
        else:
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
        flecha = "▾" if expandida else "▸"
        return f"{flecha} — {categoria.upper()} —"

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
        """F2: una sola instancia por ventana — F2 repetido mientras ya
        está abierta la vuelve a traer al frente en vez de abrir una
        segunda, y `_calculadora` queda en `None` otra vez cuando se la
        cierra con la cruz (señal `destroyed`) para que la próxima F2
        abra una nueva."""
        if self._calculadora is None:
            self._calculadora = Calculadora(self)
            self._calculadora.destroyed.connect(self._al_cerrar_calculadora)
            self._calculadora.show()
        else:
            self._calculadora.raise_()
            self._calculadora.activateWindow()

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
            if self._secciones[indice_pila].nombre == nombre:
                categoria = self._secciones[indice_pila].categoria
                if not self._categorias_expandidas.get(categoria, True):
                    self._categorias_expandidas[categoria] = True
                    self._aplicar_colapso(categoria)
                self._navegacion.setCurrentRow(fila)
                return self._pila.widget(indice_pila)
        return None

    def _mostrar_ayuda(self) -> None:
        """Ayuda contextual (Etapa 11): F1 muestra el texto de ayuda de
        la pantalla actualmente visible, tomado de Seccion.ayuda — salvo
        que se haya personalizado desde "Textos del sistema" (pedido de
        la clienta, ver `app.negocio.plantillas_texto`)."""
        indice_pila = self._pila.currentIndex()
        if indice_pila < 0 or indice_pila >= len(self._secciones):
            return
        seccion = self._secciones[indice_pila]
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
        momento durante la sesión."""
        cfg = self.conn.execute(
            "SELECT ModoFechaFicticia, FechaFicticia FROM Configuracion WHERE IdConfiguracion = 1"
        ).fetchone()
        activo = bool(cfg and cfg["ModoFechaFicticia"] and cfg["FechaFicticia"])
        if activo:
            self._barra_fecha_ficticia.setText(
                f"⚠ MODO FECHA FICTICIA ACTIVO — Hoy simulado: {cfg['FechaFicticia']} ⚠"
            )
        self._barra_fecha_ficticia.setVisible(activo)

    def _actualizar_badge_periodo(self) -> None:
        """Miscelánea (ago-2026): el período en el que está posicionado el
        sistema tiene que estar siempre a la vista en cualquier pantalla —
        se revisa en cada cambio de sección, igual que la barra de fecha
        ficticia, para que un avance de mes se refleje sin reiniciar."""
        self._badge_periodo.setText(f"Período {self._periodo_legible()}")

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
