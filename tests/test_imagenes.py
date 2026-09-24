from pathlib import Path

import pytest

from app.negocio.imagenes import (
    agregar_enlace,
    agregar_imagen,
    alternar_activo,
    categorias_por_alcance,
    eliminar_imagen,
    es_documento,
    es_enlace,
    es_imagen,
    imagenes_del_alcance,
    imagenes_todas,
    marcar_principal,
    obtener_principal,
    reordenar,
)
from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.repositorio.registro import obtener_repositorio


@pytest.fixture
def conn(tmp_path):
    connection = init_database(tmp_path / "test.db")
    sembrar_valores_por_defecto(connection)
    yield connection
    connection.close()


@pytest.fixture
def consultorio(conn):
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    id_unidad = obtener_repositorio(conn, "Unidad").crear(IdEdificio=id_edificio, Departamento='7mo "L"')
    return obtener_repositorio(conn, "Consultorio").crear(IdUnidad=id_unidad, NumeroConsultorio=1)


def _archivo_jpg(tmp_path, nombre="foto.jpg", contenido=b"x" * 100) -> str:
    tmp_path.mkdir(parents=True, exist_ok=True)
    ruta = tmp_path / nombre
    ruta.write_bytes(contenido)
    return str(ruta)


def _configurar_carpeta_base(conn, ruta) -> None:
    obtener_repositorio(conn, "Configuracion").actualizar(1, CarpetaBaseArchivos=str(ruta))


def test_agregar_imagen_sin_alcance_es_espacio_y_se_guarda(conn, tmp_path):
    _configurar_carpeta_base(conn, tmp_path / "base")
    id_imagen = agregar_imagen(conn, ruta_origen=_archivo_jpg(tmp_path / "origen"), categoria="Logo PDF")

    fila = obtener_repositorio(conn, "Imagen").obtener(id_imagen)
    assert fila["IdLocalidad"] is None
    assert fila["IdEdificio"] is None
    assert fila["IdUnidad"] is None
    assert fila["IdConsultorio"] is None
    assert Path(fila["RutaArchivo"]).parent.name == "Espacio"


def test_agregar_imagen_de_localidad_usa_el_id_como_carpeta(conn, tmp_path):
    _configurar_carpeta_base(conn, tmp_path / "base")
    id_localidad = obtener_repositorio(conn, "Localidad").crear(Localidad="Rosario")
    id_imagen = agregar_imagen(
        conn, ruta_origen=_archivo_jpg(tmp_path / "origen"), categoria="Logo PDF", id_localidad=id_localidad,
    )

    fila = obtener_repositorio(conn, "Imagen").obtener(id_imagen)
    assert fila["IdLocalidad"] == id_localidad
    assert Path(fila["RutaArchivo"]).parent.name == f"Localidad_{id_localidad}"


def test_imagenes_del_alcance_espacio_no_incluye_las_de_localidad(conn, tmp_path):
    _configurar_carpeta_base(conn, tmp_path / "base")
    id_localidad = obtener_repositorio(conn, "Localidad").crear(Localidad="Rosario")
    agregar_imagen(conn, ruta_origen=_archivo_jpg(tmp_path / "origen", "a.jpg"), categoria="Logo PDF")
    agregar_imagen(
        conn, ruta_origen=_archivo_jpg(tmp_path / "origen", "b.jpg"), categoria="Logo PDF", id_localidad=id_localidad,
    )

    assert len(imagenes_del_alcance(conn)) == 1
    assert len(imagenes_del_alcance(conn, id_localidad=id_localidad)) == 1


def test_agregar_imagen_con_dos_alcances_falla(conn, consultorio, tmp_path):
    _configurar_carpeta_base(conn, tmp_path)
    with pytest.raises(ValueError):
        agregar_imagen(
            conn, ruta_origen=_archivo_jpg(tmp_path), categoria="Foto general", id_consultorio=consultorio, id_edificio=1,
        )


def test_agregar_imagen_copia_el_archivo_y_arma_la_descripcion_sola(conn, consultorio, tmp_path):
    _configurar_carpeta_base(conn, tmp_path / "base")
    origen = _archivo_jpg(tmp_path / "origen")

    id_imagen = agregar_imagen(conn, ruta_origen=origen, categoria="Foto general", id_consultorio=consultorio)

    fila = obtener_repositorio(conn, "Imagen").obtener(id_imagen)
    assert fila["Descripcion"] == "Consultorio - Foto general - 1"
    assert fila["NumeroOrden"] == 1
    assert fila["Activo"] == 1
    ruta_copia = Path(fila["RutaArchivo"])
    assert ruta_copia.is_file()
    assert ruta_copia != Path(origen)  # se copió, no referenció el original
    assert ruta_copia.stem == "Consultorio - Foto general - 1"  # el nombre de archivo sale de la descripción


def test_agregar_imagen_formato_no_soportado_falla(conn, consultorio, tmp_path):
    _configurar_carpeta_base(conn, tmp_path)
    ruta = tmp_path / "documento.xlsx"
    ruta.write_bytes(b"x")
    with pytest.raises(ValueError):
        agregar_imagen(conn, ruta_origen=str(ruta), categoria="Foto general", id_consultorio=consultorio)


def test_agregar_imagen_supera_tamano_maximo_falla(conn, consultorio, tmp_path):
    _configurar_carpeta_base(conn, tmp_path)
    obtener_repositorio(conn, "Configuracion").actualizar(1, TamanoMaximoImagenMB=0.00001)
    with pytest.raises(ValueError):
        agregar_imagen(conn, ruta_origen=_archivo_jpg(tmp_path), categoria="Foto general", id_consultorio=consultorio)


def test_agregar_dos_imagenes_de_la_misma_categoria_incrementa_el_orden(conn, consultorio, tmp_path):
    _configurar_carpeta_base(conn, tmp_path / "base")
    origen_dir = tmp_path / "origen"
    origen_dir.mkdir()
    id1 = agregar_imagen(conn, ruta_origen=_archivo_jpg(origen_dir, "a.jpg"), categoria="Foto general", id_consultorio=consultorio)
    id2 = agregar_imagen(conn, ruta_origen=_archivo_jpg(origen_dir, "b.jpg"), categoria="Foto general", id_consultorio=consultorio)

    repo = obtener_repositorio(conn, "Imagen")
    assert repo.obtener(id1)["NumeroOrden"] == 1
    assert repo.obtener(id2)["NumeroOrden"] == 2


def test_agregar_imagen_de_otra_categoria_empieza_su_propio_orden(conn, consultorio, tmp_path):
    """El número de orden (y quién es la "principal") es propio de cada
    categoría dentro del mismo alcance/entidad — Ventana no compite con
    Foto general."""
    _configurar_carpeta_base(conn, tmp_path / "base")
    origen_dir = tmp_path / "origen"
    origen_dir.mkdir()
    agregar_imagen(conn, ruta_origen=_archivo_jpg(origen_dir, "a.jpg"), categoria="Foto general", id_consultorio=consultorio)
    id_ventana = agregar_imagen(conn, ruta_origen=_archivo_jpg(origen_dir, "b.jpg"), categoria="Ventana", id_consultorio=consultorio)

    fila = obtener_repositorio(conn, "Imagen").obtener(id_ventana)
    assert fila["NumeroOrden"] == 1
    assert fila["Descripcion"] == "Consultorio - Ventana - 1"


def test_agregar_imagen_marcando_principal_desplaza_a_la_anterior(conn, consultorio, tmp_path):
    _configurar_carpeta_base(conn, tmp_path / "base")
    origen_dir = tmp_path / "origen"
    origen_dir.mkdir()
    id1 = agregar_imagen(conn, ruta_origen=_archivo_jpg(origen_dir, "a.jpg"), categoria="Foto general", id_consultorio=consultorio)
    id2 = agregar_imagen(
        conn, ruta_origen=_archivo_jpg(origen_dir, "b.jpg"), categoria="Foto general", id_consultorio=consultorio,
        principal=True,
    )

    repo = obtener_repositorio(conn, "Imagen")
    assert repo.obtener(id2)["NumeroOrden"] == 1
    assert repo.obtener(id1)["NumeroOrden"] == 2
    assert repo.obtener(id1)["Descripcion"] == "Consultorio - Foto general - 2"


def test_marcar_principal_intercambia_y_renombra_los_dos_archivos(conn, consultorio, tmp_path):
    _configurar_carpeta_base(conn, tmp_path / "base")
    origen_dir = tmp_path / "origen"
    origen_dir.mkdir()
    id1 = agregar_imagen(conn, ruta_origen=_archivo_jpg(origen_dir, "a.jpg"), categoria="Foto general", id_consultorio=consultorio)
    id2 = agregar_imagen(conn, ruta_origen=_archivo_jpg(origen_dir, "b.jpg"), categoria="Foto general", id_consultorio=consultorio)

    marcar_principal(conn, id2)

    repo = obtener_repositorio(conn, "Imagen")
    fila1, fila2 = repo.obtener(id1), repo.obtener(id2)
    assert fila2["NumeroOrden"] == 1
    assert fila1["NumeroOrden"] == 2
    assert Path(fila2["RutaArchivo"]).stem == "Consultorio - Foto general - 1"
    assert Path(fila1["RutaArchivo"]).stem == "Consultorio - Foto general - 2"
    assert Path(fila2["RutaArchivo"]).is_file()
    assert Path(fila1["RutaArchivo"]).is_file()


def test_obtener_principal_de_localidad_cae_al_de_espacio_si_no_tiene_propio(conn, tmp_path):
    _configurar_carpeta_base(conn, tmp_path / "base")
    id_localidad = obtener_repositorio(conn, "Localidad").crear(Localidad="Rosario")
    id_logo_espacio = agregar_imagen(conn, ruta_origen=_archivo_jpg(tmp_path / "origen", "a.jpg"), categoria="Logo PDF")

    principal = obtener_principal(conn, "Logo PDF", id_localidad=id_localidad)
    assert principal["IdImagen"] == id_logo_espacio


def test_obtener_principal_de_localidad_pisa_al_de_espacio_si_tiene_propio(conn, tmp_path):
    _configurar_carpeta_base(conn, tmp_path / "base")
    id_localidad = obtener_repositorio(conn, "Localidad").crear(Localidad="Rosario")
    agregar_imagen(conn, ruta_origen=_archivo_jpg(tmp_path / "origen", "a.jpg"), categoria="Logo PDF")
    id_logo_localidad = agregar_imagen(
        conn, ruta_origen=_archivo_jpg(tmp_path / "origen", "b.jpg"), categoria="Logo PDF", id_localidad=id_localidad,
    )

    principal = obtener_principal(conn, "Logo PDF", id_localidad=id_localidad)
    assert principal["IdImagen"] == id_logo_localidad


def test_obtener_principal_de_edificio_no_tiene_respaldo(conn, tmp_path):
    """A diferencia de Localidad, Edificio/Unidad/Consultorio no caen a
    ningún nivel superior si no tienen la categoría cargada."""
    _configurar_carpeta_base(conn, tmp_path / "base")
    id_edificio = obtener_repositorio(conn, "Edificio").crear(Nombre="Ramos 1")
    assert obtener_principal(conn, "Fachada", id_edificio=id_edificio) is None


def test_imagenes_todas_incluye_todos_los_niveles_ordenadas(conn, consultorio, tmp_path):
    _configurar_carpeta_base(conn, tmp_path / "base")
    agregar_imagen(conn, ruta_origen=_archivo_jpg(tmp_path / "origen", "a.jpg"), categoria="Logo PDF")
    agregar_imagen(conn, ruta_origen=_archivo_jpg(tmp_path / "origen", "b.jpg"), categoria="Foto general", id_consultorio=consultorio)

    filas = imagenes_todas(conn)
    assert [f["Alcance"] for f in filas] == ["Espacio", "Consultorio"]
    fila_consultorio = filas[1]
    assert fila_consultorio["EdificioTexto"] == "Ramos 1"
    assert fila_consultorio["UnidadTexto"] == '7mo "L"'
    assert fila_consultorio["ConsultorioNumero"] == 1


def test_agregar_mismo_nombre_no_pisa_el_archivo_anterior(conn, consultorio, tmp_path):
    _configurar_carpeta_base(conn, tmp_path / "base")
    origen1 = tmp_path / "a.jpg"
    origen1.write_bytes(b"primero")
    id1 = agregar_imagen(conn, ruta_origen=str(origen1), categoria="Foto general", id_consultorio=consultorio)
    origen1.write_bytes(b"segundo")  # mismo nombre, otro contenido
    id2 = agregar_imagen(conn, ruta_origen=str(origen1), categoria="Foto general", id_consultorio=consultorio)

    repo = obtener_repositorio(conn, "Imagen")
    ruta1 = Path(repo.obtener(id1)["RutaArchivo"])
    ruta2 = Path(repo.obtener(id2)["RutaArchivo"])
    assert ruta1 != ruta2
    assert ruta1.read_bytes() == b"primero"
    assert ruta2.read_bytes() == b"segundo"


def test_eliminar_imagen_borra_fila_y_archivo(conn, consultorio, tmp_path):
    _configurar_carpeta_base(conn, tmp_path / "base")
    id_imagen = agregar_imagen(conn, ruta_origen=_archivo_jpg(tmp_path / "origen"), categoria="Foto general", id_consultorio=consultorio)
    ruta = Path(obtener_repositorio(conn, "Imagen").obtener(id_imagen)["RutaArchivo"])

    eliminar_imagen(conn, id_imagen)

    assert obtener_repositorio(conn, "Imagen").obtener(id_imagen) is None
    assert not ruta.is_file()


def test_reordenar_intercambia_numero_orden_y_renombra(conn, consultorio, tmp_path):
    _configurar_carpeta_base(conn, tmp_path / "base")
    origen_dir = tmp_path / "origen"
    origen_dir.mkdir()
    id1 = agregar_imagen(conn, ruta_origen=_archivo_jpg(origen_dir, "a.jpg"), categoria="Foto general", id_consultorio=consultorio)
    id2 = agregar_imagen(conn, ruta_origen=_archivo_jpg(origen_dir, "b.jpg"), categoria="Foto general", id_consultorio=consultorio)

    reordenar(conn, id2, -1)  # sube la segunda al primer lugar

    repo = obtener_repositorio(conn, "Imagen")
    assert repo.obtener(id1)["NumeroOrden"] == 2
    assert repo.obtener(id2)["NumeroOrden"] == 1
    assert Path(repo.obtener(id2)["RutaArchivo"]).stem == "Consultorio - Foto general - 1"


def test_reordenar_en_el_extremo_no_hace_nada(conn, consultorio, tmp_path):
    _configurar_carpeta_base(conn, tmp_path)
    id1 = agregar_imagen(conn, ruta_origen=_archivo_jpg(tmp_path / "origen"), categoria="Foto general", id_consultorio=consultorio)
    reordenar(conn, id1, -1)  # ya es la primera, no hay a dónde subir
    assert obtener_repositorio(conn, "Imagen").obtener(id1)["NumeroOrden"] == 1


def test_reordenar_no_mezcla_categorias_distintas(conn, consultorio, tmp_path):
    _configurar_carpeta_base(conn, tmp_path / "base")
    origen_dir = tmp_path / "origen"
    origen_dir.mkdir()
    id_foto = agregar_imagen(conn, ruta_origen=_archivo_jpg(origen_dir, "a.jpg"), categoria="Foto general", id_consultorio=consultorio)
    reordenar(conn, id_foto, -1)  # es la única de su categoría: no hay con quién intercambiar
    assert obtener_repositorio(conn, "Imagen").obtener(id_foto)["NumeroOrden"] == 1


def test_alternar_activo(conn, consultorio, tmp_path):
    _configurar_carpeta_base(conn, tmp_path)
    id_imagen = agregar_imagen(conn, ruta_origen=_archivo_jpg(tmp_path / "origen"), categoria="Foto general", id_consultorio=consultorio)
    alternar_activo(conn, id_imagen)
    assert obtener_repositorio(conn, "Imagen").obtener(id_imagen)["Activo"] == 0
    alternar_activo(conn, id_imagen)
    assert obtener_repositorio(conn, "Imagen").obtener(id_imagen)["Activo"] == 1


def test_imagenes_del_alcance_trae_activas_e_inactivas(conn, consultorio, tmp_path):
    _configurar_carpeta_base(conn, tmp_path)
    id_imagen = agregar_imagen(conn, ruta_origen=_archivo_jpg(tmp_path / "origen"), categoria="Foto general", id_consultorio=consultorio)
    alternar_activo(conn, id_imagen)
    filas = imagenes_del_alcance(conn, id_consultorio=consultorio)
    assert len(filas) == 1


def _archivo_pdf(tmp_path, nombre="doc.pdf") -> str:
    tmp_path.mkdir(parents=True, exist_ok=True)
    ruta = tmp_path / nombre
    ruta.write_bytes(b"%PDF-1.4 contenido de prueba")
    return str(ruta)


def test_es_imagen_y_es_documento_por_extension():
    assert es_imagen("foto.jpg") and not es_documento("foto.jpg")
    assert es_documento("manual.pdf") and not es_imagen("manual.pdf")
    assert es_documento("planos.docx")
    assert es_documento("notas.txt")


def test_categorias_por_alcance_imagen_y_documento():
    assert "Fachada" in categorias_por_alcance("Edificio", "Imagen")
    assert "Planos de instalación" in categorias_por_alcance("Unidad", "Documento")
    assert "Habilitación" in categorias_por_alcance("Unidad", "Documento")
    assert "Manual del usuario" in categorias_por_alcance("Espacio", "Documento")
    assert categorias_por_alcance("Localidad", "Documento") == ["Otros documentos"]


def test_agregar_documento_pdf_se_guarda_como_documento(conn, consultorio, tmp_path):
    _configurar_carpeta_base(conn, tmp_path / "base")
    id_imagen = agregar_imagen(
        conn, ruta_origen=_archivo_pdf(tmp_path / "origen"), categoria="Otros documentos",
        etiqueta_libre="Habilitación municipal", id_consultorio=consultorio,
    )
    fila = obtener_repositorio(conn, "Imagen").obtener(id_imagen)
    assert fila["Descripcion"] == "Consultorio - Otros documentos - Habilitación municipal - 1"
    assert Path(fila["RutaArchivo"]).suffix == ".pdf"
    assert es_documento(fila["RutaArchivo"])


def test_agregar_otros_documentos_sin_etiqueta_falla(conn, consultorio, tmp_path):
    _configurar_carpeta_base(conn, tmp_path)
    with pytest.raises(ValueError):
        agregar_imagen(
            conn, ruta_origen=_archivo_pdf(tmp_path), categoria="Otros documentos", id_consultorio=consultorio,
        )


def test_es_enlace_por_prefijo_http():
    assert es_enlace("https://youtu.be/abc123")
    assert es_enlace("http://youtu.be/abc123")
    assert not es_enlace("foto.jpg")
    assert not es_enlace("")
    assert not es_enlace(None)


def test_categorias_por_alcance_enlace():
    assert "Recorrido de la unidad" in categorias_por_alcance("Unidad", "Enlace")
    assert "Recorrido del consultorio" in categorias_por_alcance("Consultorio", "Enlace")
    assert "Otros enlaces" in categorias_por_alcance("Espacio", "Enlace")


def test_agregar_enlace_guarda_la_url_sin_corromperla(conn, consultorio):
    """Pasar una URL por `pathlib.Path` colapsa el "//" de "https://" a
    un solo "/" — `agregar_enlace` no puede pasar por ese camino."""
    url = "https://youtu.be/abc123?t=5"
    id_imagen = agregar_enlace(conn, url=url, categoria="Recorrido del consultorio", id_consultorio=consultorio)

    fila = obtener_repositorio(conn, "Imagen").obtener(id_imagen)
    assert fila["RutaArchivo"] == url
    assert fila["Descripcion"] == "Consultorio - Recorrido del consultorio - 1"
    assert fila["NumeroOrden"] == 1


def test_agregar_enlace_sin_prefijo_http_falla(conn, consultorio):
    with pytest.raises(ValueError):
        agregar_enlace(conn, url="youtu.be/abc123", categoria="Recorrido del consultorio", id_consultorio=consultorio)


def test_agregar_enlace_otros_enlaces_sin_etiqueta_falla(conn, consultorio):
    with pytest.raises(ValueError):
        agregar_enlace(conn, url="https://youtu.be/abc123", categoria="Otros enlaces", id_consultorio=consultorio)


def test_agregar_dos_enlaces_de_la_misma_categoria_incrementa_el_orden(conn, consultorio):
    id1 = agregar_enlace(conn, url="https://youtu.be/a", categoria="Recorrido del consultorio", id_consultorio=consultorio)
    id2 = agregar_enlace(conn, url="https://youtu.be/b", categoria="Recorrido del consultorio", id_consultorio=consultorio)

    repo = obtener_repositorio(conn, "Imagen")
    assert repo.obtener(id1)["NumeroOrden"] == 1
    assert repo.obtener(id2)["NumeroOrden"] == 2


def test_marcar_principal_intercambia_dos_enlaces_sin_corromper_las_urls(conn, consultorio):
    id1 = agregar_enlace(conn, url="https://youtu.be/a", categoria="Recorrido del consultorio", id_consultorio=consultorio)
    id2 = agregar_enlace(conn, url="https://youtu.be/b", categoria="Recorrido del consultorio", id_consultorio=consultorio)

    marcar_principal(conn, id2)

    repo = obtener_repositorio(conn, "Imagen")
    fila1, fila2 = repo.obtener(id1), repo.obtener(id2)
    assert fila2["NumeroOrden"] == 1
    assert fila1["NumeroOrden"] == 2
    assert fila1["RutaArchivo"] == "https://youtu.be/a"
    assert fila2["RutaArchivo"] == "https://youtu.be/b"
    assert fila2["Descripcion"] == "Consultorio - Recorrido del consultorio - 1"
    assert fila1["Descripcion"] == "Consultorio - Recorrido del consultorio - 2"


def test_reordenar_enlaces_no_corrompe_la_url(conn, consultorio):
    id1 = agregar_enlace(conn, url="https://youtu.be/a", categoria="Recorrido del consultorio", id_consultorio=consultorio)
    id2 = agregar_enlace(conn, url="https://youtu.be/b", categoria="Recorrido del consultorio", id_consultorio=consultorio)

    reordenar(conn, id2, -1)  # sube el segundo enlace al primer lugar

    repo = obtener_repositorio(conn, "Imagen")
    assert repo.obtener(id2)["NumeroOrden"] == 1
    assert repo.obtener(id2)["RutaArchivo"] == "https://youtu.be/b"
    assert repo.obtener(id1)["RutaArchivo"] == "https://youtu.be/a"


def test_eliminar_enlace_borra_solo_la_fila(conn, consultorio):
    id_imagen = agregar_enlace(conn, url="https://youtu.be/a", categoria="Recorrido del consultorio", id_consultorio=consultorio)
    eliminar_imagen(conn, id_imagen)
    assert obtener_repositorio(conn, "Imagen").obtener(id_imagen) is None


def test_imagenes_del_alcance_incluye_enlaces_junto_con_imagenes(conn, consultorio, tmp_path):
    _configurar_carpeta_base(conn, tmp_path / "base")
    agregar_imagen(conn, ruta_origen=_archivo_jpg(tmp_path / "origen"), categoria="Foto general", id_consultorio=consultorio)
    agregar_enlace(conn, url="https://youtu.be/a", categoria="Recorrido del consultorio", id_consultorio=consultorio)

    filas = imagenes_del_alcance(conn, id_consultorio=consultorio)
    assert len(filas) == 2
    assert any(es_enlace(f["RutaArchivo"]) for f in filas)


def test_agregar_word_y_txt_son_formatos_soportados(conn, consultorio, tmp_path):
    _configurar_carpeta_base(conn, tmp_path / "base")
    origen_docx = tmp_path / "origen" / "manual.docx"
    origen_docx.parent.mkdir(parents=True, exist_ok=True)
    origen_docx.write_bytes(b"contenido")
    origen_txt = tmp_path / "origen" / "notas.txt"
    origen_txt.write_text("hola")

    id_docx = agregar_imagen(conn, ruta_origen=str(origen_docx), categoria="Foto general", id_consultorio=consultorio)
    id_txt = agregar_imagen(conn, ruta_origen=str(origen_txt), categoria="Foto general", id_consultorio=consultorio)

    repo = obtener_repositorio(conn, "Imagen")
    assert Path(repo.obtener(id_docx)["RutaArchivo"]).suffix == ".docx"
    assert Path(repo.obtener(id_txt)["RutaArchivo"]).suffix == ".txt"
