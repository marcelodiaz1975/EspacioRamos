import pytest

from app.negocio.instancia_unica import BloqueoInstanciaUnica, InstanciaYaAbierta


def test_adquirir_crea_el_archivo_de_lock(tmp_path):
    db_path = tmp_path / "espacio_ramos.db"
    bloqueo = BloqueoInstanciaUnica(db_path)
    bloqueo.adquirir()
    try:
        assert bloqueo.ruta_lock.is_file()
        assert bloqueo.ruta_lock.name == "espacio_ramos.db.lock"
    finally:
        bloqueo.liberar()


def test_segunda_instancia_sobre_la_misma_base_falla(tmp_path):
    db_path = tmp_path / "espacio_ramos.db"
    primera = BloqueoInstanciaUnica(db_path)
    primera.adquirir()
    try:
        segunda = BloqueoInstanciaUnica(db_path)
        with pytest.raises(InstanciaYaAbierta):
            segunda.adquirir()
    finally:
        primera.liberar()


def test_liberar_permite_que_otra_instancia_adquiera_despues(tmp_path):
    db_path = tmp_path / "espacio_ramos.db"
    primera = BloqueoInstanciaUnica(db_path)
    primera.adquirir()
    primera.liberar()

    segunda = BloqueoInstanciaUnica(db_path)
    segunda.adquirir()  # no debe lanzar: la primera ya liberó
    segunda.liberar()


def test_bases_de_datos_distintas_no_interfieren(tmp_path):
    bloqueo_a = BloqueoInstanciaUnica(tmp_path / "a.db")
    bloqueo_b = BloqueoInstanciaUnica(tmp_path / "b.db")
    bloqueo_a.adquirir()
    try:
        bloqueo_b.adquirir()  # base distinta: no debe lanzar
        bloqueo_b.liberar()
    finally:
        bloqueo_a.liberar()


def test_liberar_sin_adquirir_no_falla(tmp_path):
    bloqueo = BloqueoInstanciaUnica(tmp_path / "espacio_ramos.db")
    bloqueo.liberar()  # no debe lanzar


def test_uso_como_context_manager(tmp_path):
    db_path = tmp_path / "espacio_ramos.db"
    with BloqueoInstanciaUnica(db_path) as bloqueo:
        assert bloqueo.ruta_lock.is_file()
        segunda = BloqueoInstanciaUnica(db_path)
        with pytest.raises(InstanciaYaAbierta):
            segunda.adquirir()

    # al salir del "with" se liberó: ahora sí se puede adquirir
    tercera = BloqueoInstanciaUnica(db_path)
    tercera.adquirir()
    tercera.liberar()


def test_adquirir_dos_veces_seguidas_en_la_misma_instancia_no_bloquea_a_si_misma(tmp_path):
    """flock/msvcrt son advisory por descriptor de archivo — reabrir con
    la misma instancia (mismo objeto, mismo lock ya en uso) no debería
    verse afectado por llamados repetidos si se libera bien entre medio."""
    db_path = tmp_path / "espacio_ramos.db"
    bloqueo = BloqueoInstanciaUnica(db_path)
    bloqueo.adquirir()
    bloqueo.liberar()
    bloqueo.adquirir()
    bloqueo.liberar()
