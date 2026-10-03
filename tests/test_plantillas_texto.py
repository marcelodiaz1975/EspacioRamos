import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.mensajes import mensaje_detalle_reserva_aislada, mensaje_envio_liquidacion, mensaje_grupal
from app.negocio.plantillas_texto import (
    MENSAJES_EDITABLES,
    guardar_texto_personalizado,
    obtener_texto_personalizado,
    resolver_plantilla,
    sustituir_variables,
)
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


def test_sustituir_variables_reemplaza_todas_las_ocurrencias():
    assert sustituir_variables("Hola {nombre}, {nombre}!", {"nombre": "Ana"}) == "Hola Ana, Ana!"


def test_resolver_plantilla_sin_personalizar_devuelve_el_default(conn):
    assert resolver_plantilla(conn, "mensaje_situacion_1", "DEFAULT") == "DEFAULT"


def test_resolver_plantilla_personalizada_devuelve_el_override(conn):
    guardar_texto_personalizado(conn, "mensaje_situacion_1", "Texto a medida")
    assert resolver_plantilla(conn, "mensaje_situacion_1", "DEFAULT") == "Texto a medida"


def test_guardar_texto_vacio_restablece_al_default(conn):
    guardar_texto_personalizado(conn, "mensaje_situacion_1", "Texto a medida")
    guardar_texto_personalizado(conn, "mensaje_situacion_1", "")
    assert resolver_plantilla(conn, "mensaje_situacion_1", "DEFAULT") == "DEFAULT"
    assert obtener_repositorio(conn, "PlantillaTexto").listar(Clave="mensaje_situacion_1") == []


def test_guardar_texto_none_restablece_al_default(conn):
    guardar_texto_personalizado(conn, "mensaje_situacion_1", "Texto a medida")
    guardar_texto_personalizado(conn, "mensaje_situacion_1", None)
    assert obtener_texto_personalizado(conn, "mensaje_situacion_1") is None


def test_guardar_dos_veces_actualiza_la_misma_fila(conn):
    guardar_texto_personalizado(conn, "mensaje_situacion_1", "Primero")
    guardar_texto_personalizado(conn, "mensaje_situacion_1", "Segundo")
    filas = obtener_repositorio(conn, "PlantillaTexto").listar(Clave="mensaje_situacion_1")
    assert len(filas) == 1
    assert filas[0]["TextoPersonalizado"] == "Segundo"


def test_claves_de_mensajes_editables_son_unicas():
    claves = [m.clave for m in MENSAJES_EDITABLES]
    assert len(claves) == len(set(claves)) == 8


# --------------------------------------------- mensajes que usan la plantilla personalizada

def test_mensaje_envio_liquidacion_usa_plantilla_personalizada(conn):
    guardar_texto_personalizado(conn, "mensaje_envio_liquidacion", "Mes: {mes}. Gracias.")
    id_prof = obtener_repositorio(conn, "Profesional").crear(CategoriaProfesional="R", Apellido="Test")
    texto = mensaje_envio_liquidacion(conn, id_prof, "2026-08")
    assert texto == "Mes: agosto. Gracias."


def test_mensaje_grupal_bloque_feriados_sigue_armando_el_sistema(conn):
    """Aunque se personalice la plantilla, {bloque_feriados} lo sigue
    calculando el código — la clienta pidió explícitamente que las
    condiciones no queden editables."""
    guardar_texto_personalizado(conn, "mensaje_grupal", "Resumen de {mes}.{bloque_feriados}")
    obtener_repositorio(conn, "FechasEspeciales").crear(Fecha="2026-09-07", Tipo="Feriado nacional")
    texto = mensaje_grupal(conn, "2026-08")
    assert texto.startswith("Resumen de septiembre.")
    assert "FERIADOS MES DE SEPTIEMBRE" in texto


def test_mensaje_grupal_sin_personalizar_sigue_igual_que_antes(conn):
    texto = mensaje_grupal(conn, "2026-08")
    assert "LIQUIDACIONES DE SEPTIEMBRE - AVISOS VARIOS" in texto


def test_mensaje_detalle_reserva_aislada_solo_el_encabezado_es_editable(conn):
    """{detalle_items} (loops de reservas/llaves/pagos/etc.) lo sigue
    armando el código — acá solo se personaliza el encabezado, mismo
    criterio que {bloque_feriados} en el Mensaje grupal."""
    guardar_texto_personalizado(
        conn, "mensaje_detalle_reserva_aislada", "{nombre_profesional} - {mes_mayus}\n\n{detalle_items}",
    )
    id_prof = obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="A", Apellido="Test", NombrePila="Juan",
    )
    texto = mensaje_detalle_reserva_aislada(conn, id_profesional=id_prof, periodo="2026-08")
    assert texto.startswith("JUAN TEST - AGOSTO\n\n")
    assert "SALDO A ABONAR" in texto


def test_mensaje_detalle_reserva_aislada_sin_personalizar_sigue_igual_que_antes(conn):
    id_prof = obtener_repositorio(conn, "Profesional").crear(
        CategoriaProfesional="A", Apellido="Test", NombrePila="Juan",
    )
    texto = mensaje_detalle_reserva_aislada(conn, id_profesional=id_prof, periodo="2026-08")
    lineas = texto.splitlines()
    assert lineas[0] == "DETALLE RESERVA AGOSTO"
    assert lineas[1] == "JUAN TEST"
    assert lineas[2] == ""
