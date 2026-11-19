import pytest

from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.negocio.control_pagos import (
    actualizar_instancia,
    archivar_instancia,
    crear_concepto,
    dar_de_baja_concepto,
    duplicar_para_periodo_proximo,
    editar_concepto,
    eliminar_instancia_duplicada,
    es_medio_pago_tarjeta,
    generar_instancias_periodo,
    marcar_abonada,
    resumen_conteo_vencimientos,
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



def test_duplicar_para_periodo_proximo_crea_en_blanco_solo_con_medio_de_pago(conn, unidad):
    """Pedido explícito de la clienta (confirmado): nunca copia
    Vencimiento/Importe de la instancia de origen, solo el Medio de
    pago sugerido del concepto — igual que `generar_instancias_periodo`."""
    id_concepto = crear_concepto(
        conn, nombre="Edenor", categoria="Servicios", tipo_afectacion="Unidad", id_unidad=unidad,
        medio_pago_sugerido="CA Bco Hipotecario",
    )
    generar_instancias_periodo(conn, "2026-11")
    repo = obtener_repositorio(conn, "InstanciaControlPago")
    instancia = repo.listar(IdConcepto=id_concepto, Periodo="2026-11")[0]
    actualizar_instancia(conn, instancia["IdInstancia"], vencimiento="2026-11-10", importe=5000)

    id_nueva = duplicar_para_periodo_proximo(conn, instancia["IdInstancia"])

    nueva = repo.obtener(id_nueva)
    assert nueva["Periodo"] == "2026-12"
    assert nueva["Estado"] == "Pendiente"
    assert nueva["MedioPago"] == "CA Bco Hipotecario"
    assert nueva["Vencimiento"] is None
    assert nueva["Importe"] is None


def test_duplicar_para_periodo_proximo_rechaza_si_ya_existe(conn, unidad):
    id_concepto = crear_concepto(conn, nombre="Edenor", categoria="Servicios", tipo_afectacion="Unidad", id_unidad=unidad)
    generar_instancias_periodo(conn, "2026-11")
    generar_instancias_periodo(conn, "2026-12")
    repo = obtener_repositorio(conn, "InstanciaControlPago")
    instancia = repo.listar(IdConcepto=id_concepto, Periodo="2026-11")[0]

    with pytest.raises(ValueError):
        duplicar_para_periodo_proximo(conn, instancia["IdInstancia"])


def test_eliminar_instancia_duplicada_borra_la_fila_y_su_gasto_sincronizado(conn, unidad):
    id_concepto = crear_concepto(conn, nombre="Edenor", categoria="Servicios", tipo_afectacion="Unidad", id_unidad=unidad)
    generar_instancias_periodo(conn, "2026-11")
    repo = obtener_repositorio(conn, "InstanciaControlPago")
    instancia = repo.listar(IdConcepto=id_concepto, Periodo="2026-11")[0]
    id_duplicada = duplicar_para_periodo_proximo(conn, instancia["IdInstancia"])
    actualizar_instancia(conn, id_duplicada, importe=1000)
    assert obtener_repositorio(conn, "GastoOperativo").listar(Periodo="2026-12", Concepto="Edenor") != []

    eliminar_instancia_duplicada(conn, id_duplicada)

    assert repo.obtener(id_duplicada) is None
    assert obtener_repositorio(conn, "GastoOperativo").listar(Periodo="2026-12", Concepto="Edenor") == []


def test_actualizar_instancia_estado_invalido_rechaza(conn, unidad):
    id_concepto = crear_concepto(conn, nombre="Edenor", categoria="Servicios", tipo_afectacion="Unidad", id_unidad=unidad)
    generar_instancias_periodo(conn, "2026-11")
    instancia = obtener_repositorio(conn, "InstanciaControlPago").listar(IdConcepto=id_concepto, Periodo="2026-11")[0]

    with pytest.raises(ValueError):
        actualizar_instancia(conn, instancia["IdInstancia"], estado="No existe")


def test_actualizar_instancia_estado_reabre_una_instancia_archivada(conn, unidad):
    id_concepto = crear_concepto(conn, nombre="Edenor", categoria="Servicios", tipo_afectacion="Unidad", id_unidad=unidad)
    generar_instancias_periodo(conn, "2026-11")
    repo = obtener_repositorio(conn, "InstanciaControlPago")
    instancia = repo.listar(IdConcepto=id_concepto, Periodo="2026-11")[0]
    archivar_instancia(conn, instancia["IdInstancia"])

    actualizar_instancia(conn, instancia["IdInstancia"], estado="Pendiente")

    assert repo.obtener(instancia["IdInstancia"])["Estado"] == "Pendiente"


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


def test_dos_conceptos_con_el_mismo_nombre_para_distintas_unidades_sincronizan_gastos_separados(conn, unidad):
    """Bug real reportado por la clienta: "tengo dos alquileres, uno por
    la unidad del 9no 'C' y otro por la del 15 'H', solo me muestra y
    computa la del 15 'H'" — dos conceptos con el mismo nombre
    ("Alquiler") para unidades distintas no se pueden pisar entre sí al
    sincronizar (ver `sincronizar_gasto_operativo`, antes buscaba "el
    gasto ya sincronizado" por el nombre, ahora por `IdConceptoControlPago`)."""
    id_edificio = obtener_repositorio(conn, "Unidad").obtener(unidad)["IdEdificio"]
    otra_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='15 "H"')
    id_concepto_1 = crear_concepto(conn, nombre="Alquiler", categoria="Ingresos", tipo_afectacion="Unidad", id_unidad=unidad)
    id_concepto_2 = crear_concepto(conn, nombre="Alquiler", categoria="Ingresos", tipo_afectacion="Unidad", id_unidad=otra_unidad)
    generar_instancias_periodo(conn, "2026-11")
    repo = obtener_repositorio(conn, "InstanciaControlPago")
    instancia_1 = repo.listar(IdConcepto=id_concepto_1, Periodo="2026-11")[0]
    instancia_2 = repo.listar(IdConcepto=id_concepto_2, Periodo="2026-11")[0]

    actualizar_instancia(conn, instancia_1["IdInstancia"], importe=1000)
    actualizar_instancia(conn, instancia_2["IdInstancia"], importe=2000)

    gastos = obtener_repositorio(conn, "GastoOperativo").listar(Periodo="2026-11", Concepto="Alquiler")
    assert len(gastos) == 2
    montos_por_unidad = {g["IdUnidad"]: g["Monto"] for g in gastos}
    assert montos_por_unidad[unidad] == 1000
    assert montos_por_unidad[otra_unidad] == 2000

    # Editar uno de los dos no tiene que tocar al otro.
    actualizar_instancia(conn, instancia_1["IdInstancia"], importe=1500)
    gastos = obtener_repositorio(conn, "GastoOperativo").listar(Periodo="2026-11", Concepto="Alquiler")
    montos_por_unidad = {g["IdUnidad"]: g["Monto"] for g in gastos}
    assert montos_por_unidad[unidad] == 1500
    assert montos_por_unidad[otra_unidad] == 2000

    # Vaciar el importe de uno de los dos solo borra SU gasto, no el del otro.
    actualizar_instancia(conn, instancia_1["IdInstancia"], importe=None)
    gastos = obtener_repositorio(conn, "GastoOperativo").listar(Periodo="2026-11", Concepto="Alquiler")
    assert len(gastos) == 1
    assert gastos[0]["IdUnidad"] == otra_unidad


def test_eliminar_instancia_duplicada_con_concepto_de_nombre_repetido_no_borra_el_gasto_del_otro(conn, unidad):
    """Mismo bug que el de arriba, pero en `eliminar_instancia_duplicada`
    (deshacer un "Duplicar para período próximo" hecho por error): tenía
    el mismo lookup por nombre en vez de `IdConceptoControlPago`."""
    id_edificio = obtener_repositorio(conn, "Unidad").obtener(unidad)["IdEdificio"]
    otra_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='15 "H"')
    id_concepto_1 = crear_concepto(conn, nombre="Alquiler", categoria="Ingresos", tipo_afectacion="Unidad", id_unidad=unidad)
    id_concepto_2 = crear_concepto(conn, nombre="Alquiler", categoria="Ingresos", tipo_afectacion="Unidad", id_unidad=otra_unidad)
    generar_instancias_periodo(conn, "2026-11")
    repo = obtener_repositorio(conn, "InstanciaControlPago")
    instancia_1 = repo.listar(IdConcepto=id_concepto_1, Periodo="2026-11")[0]
    instancia_2 = repo.listar(IdConcepto=id_concepto_2, Periodo="2026-11")[0]
    actualizar_instancia(conn, instancia_1["IdInstancia"], importe=1000)
    actualizar_instancia(conn, instancia_2["IdInstancia"], importe=2000)
    id_duplicada_1 = duplicar_para_periodo_proximo(conn, instancia_1["IdInstancia"])
    actualizar_instancia(conn, id_duplicada_1, importe=1200)
    id_duplicada_2 = duplicar_para_periodo_proximo(conn, instancia_2["IdInstancia"])
    actualizar_instancia(conn, id_duplicada_2, importe=2200)

    eliminar_instancia_duplicada(conn, id_duplicada_1)

    assert repo.obtener(id_duplicada_1) is None
    gastos = obtener_repositorio(conn, "GastoOperativo").listar(Periodo="2026-12", Concepto="Alquiler")
    assert len(gastos) == 1
    assert gastos[0]["Monto"] == 2200


def test_es_medio_pago_tarjeta_detecta_por_substring():
    """No por nombre exacto (el combo de Medio de pago es editable) —
    por contener "tarjeta", sin distinguir mayúsculas."""
    assert es_medio_pago_tarjeta("Tarjeta Bco Macro") is True
    assert es_medio_pago_tarjeta("tarjeta de crédito nueva") is True
    assert es_medio_pago_tarjeta("CA Bco Macro") is False
    assert es_medio_pago_tarjeta("Pago manual") is False
    assert es_medio_pago_tarjeta(None) is False


def test_generar_instancias_periodo_hereda_cuenta_id_de_la_instancia_mas_reciente(conn, unidad):
    """"Cuenta/Id" (`CampoLibre1`) es una referencia estable del
    concepto aunque viva en la tabla de instancias — se hereda sola en
    los períodos siguientes, sin volver a tipearla."""
    id_concepto = crear_concepto(conn, nombre="Edenor", categoria="Servicios", tipo_afectacion="Unidad", id_unidad=unidad)
    generar_instancias_periodo(conn, "2026-11")
    repo = obtener_repositorio(conn, "InstanciaControlPago")
    instancia_nov = repo.listar(IdConcepto=id_concepto, Periodo="2026-11")[0]
    actualizar_instancia(conn, instancia_nov["IdInstancia"], cuenta_id="12345-6")

    generar_instancias_periodo(conn, "2026-12")

    instancia_dic = repo.listar(IdConcepto=id_concepto, Periodo="2026-12")[0]
    assert instancia_dic["CampoLibre1"] == "12345-6"


def test_generar_instancias_periodo_sin_cuenta_id_previa_queda_en_blanco(conn, unidad):
    id_concepto = crear_concepto(conn, nombre="Edenor", categoria="Servicios", tipo_afectacion="Unidad", id_unidad=unidad)
    generar_instancias_periodo(conn, "2026-11")
    repo = obtener_repositorio(conn, "InstanciaControlPago")
    assert repo.listar(IdConcepto=id_concepto, Periodo="2026-11")[0]["CampoLibre1"] is None


def test_duplicar_para_periodo_proximo_copia_cuenta_id(conn, unidad):
    id_concepto = crear_concepto(conn, nombre="Edenor", categoria="Servicios", tipo_afectacion="Unidad", id_unidad=unidad)
    generar_instancias_periodo(conn, "2026-11")
    repo = obtener_repositorio(conn, "InstanciaControlPago")
    instancia = repo.listar(IdConcepto=id_concepto, Periodo="2026-11")[0]
    actualizar_instancia(conn, instancia["IdInstancia"], cuenta_id="98765-4")

    id_nuevo = duplicar_para_periodo_proximo(conn, instancia["IdInstancia"])

    assert repo.obtener(id_nuevo)["CampoLibre1"] == "98765-4"


def test_actualizar_instancia_cuenta_id_se_puede_editar_y_vaciar(conn, unidad):
    id_concepto = crear_concepto(conn, nombre="Edenor", categoria="Servicios", tipo_afectacion="Unidad", id_unidad=unidad)
    generar_instancias_periodo(conn, "2026-11")
    repo = obtener_repositorio(conn, "InstanciaControlPago")
    instancia = repo.listar(IdConcepto=id_concepto, Periodo="2026-11")[0]

    actualizar_instancia(conn, instancia["IdInstancia"], cuenta_id="11-22")
    assert repo.obtener(instancia["IdInstancia"])["CampoLibre1"] == "11-22"

    actualizar_instancia(conn, instancia["IdInstancia"], cuenta_id=None)
    assert repo.obtener(instancia["IdInstancia"])["CampoLibre1"] is None


def test_resumen_conteo_vencimientos_cuenta_los_siete_buckets(conn, unidad):
    conn.execute(
        "UPDATE Configuracion SET ModoFechaFicticia = 1, FechaFicticia = '2026-11-15' WHERE IdConfiguracion = 1"
    )
    conn.commit()
    repo = obtener_repositorio(conn, "InstanciaControlPago")

    id_sin_datos = crear_concepto(conn, nombre="Sin datos", categoria="Servicios", tipo_afectacion="Unidad", id_unidad=unidad)
    id_vencido = crear_concepto(conn, nombre="Vencido", categoria="Servicios", tipo_afectacion="Unidad", id_unidad=unidad)
    id_hoy = crear_concepto(conn, nombre="Hoy", categoria="Servicios", tipo_afectacion="Unidad", id_unidad=unidad)
    id_mañana = crear_concepto(conn, nombre="Mañana", categoria="Servicios", tipo_afectacion="Unidad", id_unidad=unidad)
    id_en_dias = crear_concepto(conn, nombre="En días", categoria="Servicios", tipo_afectacion="Unidad", id_unidad=unidad)
    id_abonado = crear_concepto(conn, nombre="Abonado", categoria="Servicios", tipo_afectacion="Unidad", id_unidad=unidad)
    id_archivado = crear_concepto(conn, nombre="Archivado", categoria="Servicios", tipo_afectacion="Unidad", id_unidad=unidad)
    generar_instancias_periodo(conn, "2026-11")

    def _instancia(id_concepto):
        return repo.listar(IdConcepto=id_concepto, Periodo="2026-11")[0]

    actualizar_instancia(conn, _instancia(id_vencido)["IdInstancia"], vencimiento="2026-11-10", importe=1000)
    actualizar_instancia(conn, _instancia(id_hoy)["IdInstancia"], vencimiento="2026-11-15", importe=1000)
    actualizar_instancia(conn, _instancia(id_mañana)["IdInstancia"], vencimiento="2026-11-16", importe=1000)
    actualizar_instancia(conn, _instancia(id_en_dias)["IdInstancia"], vencimiento="2026-11-20", importe=1000)
    marcar_abonada(conn, _instancia(id_abonado)["IdInstancia"])
    archivar_instancia(conn, _instancia(id_archivado)["IdInstancia"])
    _ = id_sin_datos  # el concepto sin datos queda Pendiente sin cargar, cuenta en "por_cargar"

    resumen = resumen_conteo_vencimientos(conn)

    assert resumen["por_cargar"] == 1
    assert resumen["vencimiento_vencido"] == 1
    assert resumen["vencimiento_hoy"] == 1
    assert resumen["vencimiento_mañana"] == 1
    assert resumen["vencimiento_en_dias"] == 1
    assert resumen["archivados"] == 1
    assert resumen["total"] == 7
