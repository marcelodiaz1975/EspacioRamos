"""CRUD genérico para las tablas del Sistema Espacio Ramos.

En vez de escribir 32 clases de repositorio casi idénticas (una por cada
entidad de la sección 3 del documento), esta clase averigua las columnas de
la tabla consultando SQLite (PRAGMA table_info) y arma las consultas en base
a esa información. Cada entidad se obtiene con `registro.obtener_repositorio`.
"""
import sqlite3


class Repositorio:
    def __init__(self, conn: sqlite3.Connection, tabla: str):
        self.conn = conn
        self.tabla = tabla
        self._columnas, self._pk = self._introspectar()

    def _introspectar(self) -> tuple[list[str], str]:
        cur = self.conn.execute(f"PRAGMA table_info({self.tabla})")
        columnas = []
        pk = None
        for fila in cur.fetchall():
            columnas.append(fila["name"])
            if fila["pk"]:
                pk = fila["name"]
        if pk is None:
            raise ValueError(f"La tabla {self.tabla} no tiene clave primaria definida")
        return columnas, pk

    @property
    def columnas(self) -> list[str]:
        return list(self._columnas)

    @property
    def clave_primaria(self) -> str:
        return self._pk

    def crear(self, **campos) -> int:
        campos = {k: v for k, v in campos.items() if k in self._columnas and v is not None}
        if not campos:
            raise ValueError("No se recibió ningún campo válido para crear el registro")
        columnas = ", ".join(campos.keys())
        placeholders = ", ".join("?" for _ in campos)
        sql = f"INSERT INTO {self.tabla} ({columnas}) VALUES ({placeholders})"
        cur = self.conn.execute(sql, list(campos.values()))
        self.conn.commit()
        return cur.lastrowid

    def obtener(self, id_valor) -> sqlite3.Row | None:
        sql = f"SELECT * FROM {self.tabla} WHERE {self._pk} = ?"
        return self.conn.execute(sql, (id_valor,)).fetchone()

    def listar(self, **filtros) -> list[sqlite3.Row]:
        filtros = {k: v for k, v in filtros.items() if k in self._columnas}
        sql = f"SELECT * FROM {self.tabla}"
        valores: list = []
        if filtros:
            condiciones = " AND ".join(f"{k} = ?" for k in filtros)
            sql += f" WHERE {condiciones}"
            valores = list(filtros.values())
        return self.conn.execute(sql, valores).fetchall()

    def actualizar(self, id_valor, **campos) -> None:
        campos = {k: v for k, v in campos.items() if k in self._columnas and k != self._pk}
        if not campos:
            return
        set_clause = ", ".join(f"{k} = ?" for k in campos)
        sql = f"UPDATE {self.tabla} SET {set_clause} WHERE {self._pk} = ?"
        self.conn.execute(sql, list(campos.values()) + [id_valor])
        self.conn.commit()

    def eliminar(self, id_valor) -> None:
        sql = f"DELETE FROM {self.tabla} WHERE {self._pk} = ?"
        self.conn.execute(sql, (id_valor,))
        self.conn.commit()
