import pytest

from app.negocio.validaciones import (
    es_cuit_valido,
    es_dni_valido,
    es_email_valido,
    es_fecha_valida,
    es_periodo_valido,
)


@pytest.mark.parametrize("texto", ["2026-09-15", "2000-01-01", "2026-02-28"])
def test_es_fecha_valida_acepta_fechas_reales(texto):
    assert es_fecha_valida(texto) is True


@pytest.mark.parametrize("texto", ["2026-02-30", "31-12-2026", "2026/09/15", "hola", "", "2026-13-01"])
def test_es_fecha_valida_rechaza_formatos_o_fechas_invalidas(texto):
    assert es_fecha_valida(texto) is False


@pytest.mark.parametrize("texto", ["2026-09", "2000-01", "2026-12"])
def test_es_periodo_valido_acepta_periodos_reales(texto):
    assert es_periodo_valido(texto) is True


@pytest.mark.parametrize("texto", ["2026-13", "2026-00", "09-2026", "2026", "hola", ""])
def test_es_periodo_valido_rechaza_formatos_invalidos(texto):
    assert es_periodo_valido(texto) is False


@pytest.mark.parametrize("texto", ["ana@ejemplo.com", "juan.perez@dominio.com.ar"])
def test_es_email_valido_acepta_emails_reales(texto):
    assert es_email_valido(texto) is True


@pytest.mark.parametrize("texto", ["ana@", "@dominio.com", "ana dominio.com", "ana@dominio", ""])
def test_es_email_valido_rechaza_formatos_invalidos(texto):
    assert es_email_valido(texto) is False


@pytest.mark.parametrize("texto", ["12345678", "1234567"])
def test_es_dni_valido_acepta_solo_digitos_en_rango(texto):
    assert es_dni_valido(texto) is True


@pytest.mark.parametrize("texto", ["12.345.678", "abc12345", "123", ""])
def test_es_dni_valido_rechaza_formatos_invalidos(texto):
    assert es_dni_valido(texto) is False


def test_es_cuit_valido_acepta_11_digitos():
    assert es_cuit_valido("20123456789") is True


@pytest.mark.parametrize("texto", ["20-12345678-9", "2012345678", "201234567890", "abc12345678", ""])
def test_es_cuit_valido_rechaza_formatos_invalidos(texto):
    assert es_cuit_valido(texto) is False
