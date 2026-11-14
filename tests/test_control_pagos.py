import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.control_pagos import (
    actualizar_instancia,
    archivar_instancia,
    crear_concepto,
    dar_de_baja_concepto,
    editar_concepto,
    generar_instancias_periodo,
    marcar_abonada,
    texto_afectacion,
)
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


@pytest.fixture
def unidad(conn):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    return obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='7mo "L"')


def test_crear_concepto_unidad_limpia_otras_referencias_de_afectacion(conn, unidad):
    id_concepto = crear_concepto(
        conn, nombre="Edenor", categoria="Servicios", tipo_afectacion="Unidad", id_unidad=unidad,
        medio_pago_sugerido="CA Bco Hipotecario",
    )
    concepto = obtener_repositorio(conn, "ConceptoControlPago").obtener(id_concepto)
    assert concepto["IdUnidad"] == unidad
    assert concepto["IdEdificio"] is None
    assert concepto["IdInmueblePersonal"] is None
    assert concepto["IdRodado"] is None
    assert concepto["IdPersonaFamilia"] is None


def test_crear_concepto_tipo_afectacion_invalido_rechaza(conn):
    with pytest.raises(ValueError):
        crear_concepto(conn, nombre="Algo", categoria=None, tipo_afectacion="No existe")


def test_texto_afectacion_unidad_edificio_personal_rodado_persona_familia(conn, unidad):
    id_concepto_unidad = crear_concepto(conn, nombre="Edenor", categoria=None, tipo_afectacion="Unidad", id_unidad=unidad)
    concepto_unidad = obtener_repositorio(conn, "ConceptoControlPago").obtener(id_concepto_unidad)
    assert texto_afectacion(conn, concepto_unidad) == 'Ramos 1 - 7mo "L"'

    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 2")
    id_concepto_edificio = crear_concepto(
        conn, nombre="Seguro edificio", categoria=None, tipo_afectacion="Edificio", id_edificio=id_edificio,
    )
    concepto_edificio = obtener_repositorio(conn, "ConceptoControlPago").obtener(id_concepto_edificio)
    assert texto_afectacion(conn, concepto_edificio) == "Ramos 2"

    id_concepto_espacio = crear_concepto(conn, nombre="Google Ads", categoria=None, tipo_afectacion="Espacio general")
    concepto_espacio = obtener_repositorio(conn, "ConceptoControlPago").obtener(id_concepto_espacio)
    assert texto_afectacion(conn, concepto_espacio) == "Espacio general"

    id_localidad = obtener_repositorio(conn, "Localidad").crear(Localidad="San Justo")
    id_inmueble = obtener_repositorio(conn, "InmueblePersonal").crear(
        TipoInmueble="Casa", Direccion="Lynch 2203", IdLocalidad=id_localidad,
    )
    id_concepto_inmueble = crear_concepto(
        conn, nombre="Edenor casa", categoria=None, tipo_afectacion="Inmueble personal",
        id_inmueble_personal=id_inmueble,
    )
    concepto_inmueble = obtener_repositorio(conn, "ConceptoControlPago").obtener(id_concepto_inmueble)
    assert texto_afectacion(conn, concepto_inmueble) == "Casa Lynch 2203, San Justo"

    id_rodado = obtener_repositorio(conn, "Rodado").crear(Marca="Renault", Modelo="Kangoo II", Dominio="AH422LE")
    id_concepto_rodado = crear_concepto(conn, nombre="Patente", categoria=None, tipo_afectacion="Rodado", id_rodado=id_rodado)
    concepto_rodado = obtener_repositorio(conn, "ConceptoControlPago").obtener(id_concepto_rodado)
    assert texto_afectacion(conn, concepto_rodado) == "Renault Kangoo II AH422LE"

    id_persona = obtener_repositorio(conn, "PersonaFamilia").crear(Nombre="Marcelo")
    id_concepto_persona = crear_concepto(
        conn, nombre="Monotributo", categoria=None, tipo_afectacion="Persona", id_persona_familia=id_persona,
    )
    concepto_persona = obtener_repositorio(conn, "ConceptoControlPago").obtener(id_concepto_persona)
    assert texto_afectacion(conn, concepto_persona) == "Marcelo"

    id_concepto_familia = crear_concepto(conn, nombre="Colegio", categoria=None, tipo_afectacion="Familia")
    concepto_familia = obtener_repositorio(conn, "ConceptoControlPago").obtener(id_concepto_familia)
    assert texto_afectacion(conn, concepto_familia) == "Familia"


def test_generar_instancias_periodo_crea_en_blanco_y_es_idempotente(conn, unidad):
    id_concepto = crear_concepto(
        conn, nombre="Edenor", categoria="Servicios", tipo_afectacion="Unidad", id_unidad=unidad,
        medio_pago_sugerido="CA Bco Hipotecario",
    )
    creadas = generar_instancias_periodo(conn, "2026-11")
    assert creadas == 1
    instancia = obtener_repositorio(conn, "InstanciaControlPago").listar(IdConcepto=id_concepto, Periodo="2026-11")[0]
    assert instancia["Vencimiento"] is None
    assert instancia["Importe"] is None
    assert instancia["Estado"] == "Pendiente"
    assert instancia["MedioPago"] == "CA Bco Hipotecario"

    assert generar_instancias_periodo(conn, "2026-11") == 0
    assert len(obtener_repositorio(conn, "InstanciaControlPago").listar(IdConcepto=id_concepto, Periodo="2026-11")) == 1


def test_concepto_dado_de_baja_no_genera_mas_instancias(conn, unidad):
    id_concepto = crear_concepto(conn, nombre="Edenor", categoria="Servicios", tipo_afectacion="Unidad", id_unidad=unidad)
    generar_instancias_periodo(conn, "2026-11")
    dar_de_baja_concepto(conn, id_concepto)
    generar_instancias_periodo(conn, "2026-12")
    assert obtener_repositorio(conn, "InstanciaControlPago").listar(IdConcepto=id_concepto, Periodo="2026-12") == []
    # El historial del período anterior (ya generado antes de la baja) no se toca.
    assert len(obtener_repositorio(conn, "InstanciaControlPago").listar(IdConcepto=id_concepto, Periodo="2026-11")) == 1


def test_actualizar_instancia_sincroniza_gasto_operativo_y_preserva_lo_no_tocado(conn, unidad):
    id_concepto = crear_concepto(
        conn, nombre="Edenor", categoria="Servicios", tipo_afectacion="Unidad", id_unidad=unidad,
        medio_pago_sugerido="CA Bco Hipotecario",
    )
    generar_instancias_periodo(conn, "2026-11")
    instancia = obtener_repositorio(conn, "InstanciaControlPago").listar(IdConcepto=id_concepto, Periodo="2026-11")[0]

    actualizar_instancia(conn, instancia["IdInstancia"], vencimiento="2026-12-02", importe=45500.26)

    gasto = obtener_repositorio(conn, "GastoOperativo").listar(Periodo="2026-11", Concepto="Edenor")
    assert len(gasto) == 1
    assert gasto[0]["Monto"] == 45500.26
    assert gasto[0]["Origen"] == "Importado"
    assert gasto[0]["Alcance"] == "Unidad"
    assert gasto[0]["IdUnidad"] == unidad

    # Editar solo el importe no tiene que tocar el medio de pago ni el vencimiento.
    actualizar_instancia(conn, instancia["IdInstancia"], importe=50000)
    actualizada = obtener_repositorio(conn, "InstanciaControlPago").obtener(instancia["IdInstancia"])
    assert actualizada["MedioPago"] == "CA Bco Hipotecario"
    assert actualizada["Vencimiento"] == "2026-12-02"
    assert actualizada["Importe"] == 50000

    # Vaciar el importe borra el gasto operativo sincronizado.
    actualizar_instancia(conn, instancia["IdInstancia"], importe=None)
    assert obtener_repositorio(conn, "GastoOperativo").listar(Periodo="2026-11", Concepto="Edenor") == []


def test_concepto_personal_nunca_sincroniza_gasto_operativo(conn):
    id_rodado = obtener_repositorio(conn, "Rodado").crear(Marca="Renault", Modelo="Kwid", Dominio="AH486AS")
    id_concepto = crear_concepto(conn, nombre="Patente", categoria="Impuestos", tipo_afectacion="Rodado", id_rodado=id_rodado)
    generar_instancias_periodo(conn, "2026-11")
    instancia = obtener_repositorio(conn, "InstanciaControlPago").listar(IdConcepto=id_concepto, Periodo="2026-11")[0]

    actualizar_instancia(conn, instancia["IdInstancia"], vencimiento="2026-11-20", importe=12000)

    assert obtener_repositorio(conn, "GastoOperativo").listar() == []


def test_archivar_instancia_sin_datos_cargados(conn, unidad):
    id_concepto = crear_concepto(conn, nombre="Expensas extraordinarias", categoria="Expensas", tipo_afectacion="Unidad", id_unidad=unidad)
    generar_instancias_periodo(conn, "2026-11")
    instancia = obtener_repositorio(conn, "InstanciaControlPago").listar(IdConcepto=id_concepto, Periodo="2026-11")[0]

    archivar_instancia(conn, instancia["IdInstancia"])

    assert obtener_repositorio(conn, "InstanciaControlPago").obtener(instancia["IdInstancia"])["Estado"] == "Archivado"


def test_archivar_instancia_con_vencimiento_o_importe_cargado_rechaza(conn, unidad):
    id_concepto = crear_concepto(conn, nombre="Edenor", categoria="Servicios", tipo_afectacion="Unidad", id_unidad=unidad)
    generar_instancias_periodo(conn, "2026-11")
    instancia = obtener_repositorio(conn, "InstanciaControlPago").listar(IdConcepto=id_concepto, Periodo="2026-11")[0]
    actualizar_instancia(conn, instancia["IdInstancia"], importe=1000)

    with pytest.raises(ValueError):
        archivar_instancia(conn, instancia["IdInstancia"])


def test_marcar_abonada(conn, unidad):
    id_concepto = crear_concepto(conn, nombre="Edenor", categoria="Servicios", tipo_afectacion="Unidad", id_unidad=unidad)
    generar_instancias_periodo(conn, "2026-11")
    instancia = obtener_repositorio(conn, "InstanciaControlPago").listar(IdConcepto=id_concepto, Periodo="2026-11")[0]

    marcar_abonada(conn, instancia["IdInstancia"])

    assert obtener_repositorio(conn, "InstanciaControlPago").obtener(instancia["IdInstancia"])["Estado"] == "Abonado"


def test_editar_concepto_cambia_afectacion_y_limpia_la_anterior(conn, unidad):
    id_concepto = crear_concepto(conn, nombre="Edenor", categoria="Servicios", tipo_afectacion="Unidad", id_unidad=unidad)
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 2")

    editar_concepto(conn, id_concepto, TipoAfectacion="Edificio", IdEdificio=id_edificio)

    concepto = obtener_repositorio(conn, "ConceptoControlPago").obtener(id_concepto)
    assert concepto["TipoAfectacion"] == "Edificio"
    assert concepto["IdEdificio"] == id_edificio
    assert concepto["IdUnidad"] is None


def test_gasto_manual_existente_no_se_pisa_al_sincronizar(conn, unidad):
    """Si ya hay un GastoOperativo Manual cargado a mano para el mismo
    Período+Concepto (ej. antes de que existiera este módulo), la
    sincronización no lo pisa ni crea un duplicado Importado en
    conflicto — respeta la regla de `gasto_en_conflicto`."""
    obtener_repositorio(conn, "GastoOperativo").crear(
        Periodo="2026-11", Categoria="Servicios", Concepto="Edenor", Monto=1000,
        Alcance="Unidad", IdUnidad=unidad, Origen="Manual",
    )
    id_concepto = crear_concepto(conn, nombre="Edenor", categoria="Servicios", tipo_afectacion="Unidad", id_unidad=unidad)
    generar_instancias_periodo(conn, "2026-11")
    instancia = obtener_repositorio(conn, "InstanciaControlPago").listar(IdConcepto=id_concepto, Periodo="2026-11")[0]

    actualizar_instancia(conn, instancia["IdInstancia"], importe=45500.26)

    gastos = obtener_repositorio(conn, "GastoOperativo").listar(Periodo="2026-11", Concepto="Edenor")
    assert len(gastos) == 1
    assert gastos[0]["Origen"] == "Manual"
    assert gastos[0]["Monto"] == 1000
