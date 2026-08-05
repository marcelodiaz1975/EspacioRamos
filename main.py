"""Herramienta de línea de comandos para tareas de administración de la base
de datos durante el desarrollo (Etapa 1). La interfaz gráfica se agrega en
una etapa posterior del plan de desarrollo."""
import argparse
from pathlib import Path

from app.db.connection import DB_PATH_DEFAULT
from app.db.init_db import init_database
from app.db.seed import sembrar_valores_por_defecto
from app.importacion.importar_excel import importar_planilla
from app.importacion.plantillas import generar_plantillas

PLANTILLA_DEFAULT = Path(__file__).resolve().parent / "plantillas_excel" / "Plantilla_Importacion_EspacioRamos.xlsx"


def comando_init_db(args):
    conn = init_database(args.db)
    sembrar_valores_por_defecto(conn)
    print(f"Base de datos inicializada en: {args.db}")


def comando_generar_plantillas(args):
    ruta = generar_plantillas(args.destino)
    print(f"Plantilla generada en: {ruta}")


def comando_importar(args):
    conn = init_database(args.db)
    sembrar_valores_por_defecto(conn)
    resultados = importar_planilla(conn, args.archivo)
    for r in resultados:
        print(f"{r.entidad}: {r.filas_importadas} fila(s) importada(s)")
        for error in r.errores:
            print(f"  ! {error}")


def main():
    parser = argparse.ArgumentParser(description="Administración de la base de datos - Sistema Espacio Ramos")
    parser.add_argument("--db", type=Path, default=DB_PATH_DEFAULT, help="Ruta al archivo de base de datos SQLite")
    subparsers = parser.add_subparsers(dest="comando", required=True)

    sp_init = subparsers.add_parser("init-db", help="Crea la base de datos y todas las tablas")
    sp_init.set_defaults(func=comando_init_db)

    sp_plant = subparsers.add_parser("generar-plantillas", help="Genera la planilla Excel de carga inicial")
    sp_plant.add_argument("--destino", type=Path, default=PLANTILLA_DEFAULT)
    sp_plant.set_defaults(func=comando_generar_plantillas)

    sp_imp = subparsers.add_parser("importar", help="Importa datos desde una planilla Excel")
    sp_imp.add_argument("archivo", type=Path)
    sp_imp.set_defaults(func=comando_importar)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
