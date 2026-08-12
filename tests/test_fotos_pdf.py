from PIL import Image as ImagenPIL

from app.pdf.fotos_pdf import RELACION_FOTO, _recortar_al_centro


def _crear_imagen(ruta, ancho, alto):
    ImagenPIL.new("RGB", (ancho, alto), color="red").save(ruta)


def test_recorta_de_los_costados_si_es_mas_ancha_que_4_3(tmp_path):
    ruta = tmp_path / "ancha.jpg"
    _crear_imagen(ruta, 1600, 900)  # 16:9, más ancha que 4:3
    resultado = _recortar_al_centro(str(ruta))
    im = ImagenPIL.open(resultado)
    assert im.size[1] == 900  # el alto no cambia
    assert abs(im.size[0] / im.size[1] - RELACION_FOTO) < 0.01
    assert im.size[0] < 1600  # se recortó ancho


def test_recorta_de_arriba_abajo_si_es_mas_alta_que_4_3(tmp_path):
    ruta = tmp_path / "alta.jpg"
    _crear_imagen(ruta, 600, 1200)  # más alta que 4:3
    resultado = _recortar_al_centro(str(ruta))
    im = ImagenPIL.open(resultado)
    assert im.size[0] == 600  # el ancho no cambia
    assert abs(im.size[0] / im.size[1] - RELACION_FOTO) < 0.01
    assert im.size[1] < 1200  # se recortó alto


def test_no_recorta_si_ya_es_4_3(tmp_path):
    ruta = tmp_path / "definitiva.jpg"
    _crear_imagen(ruta, 1200, 900)  # ya es 4:3, el formato definitivo
    resultado = _recortar_al_centro(str(ruta))
    im = ImagenPIL.open(resultado)
    assert im.size == (1200, 900)
