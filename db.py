"""
Capa de datos: aquí se guardan y se leen las multas.

Hay dos "backends" (lugares donde se guardan los datos):
  - LOCAL: una base SQLite en tu computadora. Sirve para probar la app sin nube.
  - BIGQUERY: el Data Warehouse en Google Cloud. Es el de la prueba real.

Se elige con la variable de entorno BACKEND (local o bigquery).
Las pantallas no saben cuál se usa: solo llaman a los mismos métodos.

Las columnas salen del catálogo de logic.py (34 campos + origen y fecha de carga).
Si la tabla ya existía con menos columnas, se le agregan las que faltan.
"""
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

import pandas as pd

import logic

COLUMNAS = logic.COLUMNAS_DATOS + ["fuente", "fecha_carga"]
COLUMNAS_FECHA = logic.COLUMNAS_FECHA


def _preparar(df, fuente):
    """Agrega de dónde vino el dato y cuándo se cargó."""
    d = df.copy()
    d["fuente"] = fuente
    d["fecha_carga"] = datetime.now(timezone.utc)
    return d[COLUMNAS]


def _a_fechas(df):
    """Convierte las columnas de fecha a datetime para poder calcular con ellas."""
    d = df.copy()
    for c in COLUMNAS_FECHA:
        d[c] = pd.to_datetime(d[c], errors="coerce")
    return d


# ======================================================================
# LOCAL (SQLite)
# ======================================================================
TIPO_SQLITE = {"STRING": "TEXT", "FLOAT": "REAL", "INTEGER": "INTEGER", "DATE": "TEXT",
               "TIMESTAMP": "TEXT"}


class BaseLocal:
    descripcion = "Base local (SQLite) - solo pruebas"

    def __init__(self, ruta=None):
        self.ruta = ruta or os.getenv("SQLITE_PATH", "multas_local.db")
        tipos = {c: logic.tipo_db(c) for c in logic.COLUMNAS_DATOS}
        tipos.update({"fuente": "STRING", "fecha_carga": "TIMESTAMP"})
        with closing(sqlite3.connect(self.ruta)) as con:
            columnas_sql = ", ".join(
                f"{c} {TIPO_SQLITE[tipos[c]]}" + (" PRIMARY KEY" if c == "id_multa" else "")
                for c in COLUMNAS)
            con.execute(f"CREATE TABLE IF NOT EXISTS multas ({columnas_sql})")
            # Si la tabla venía de una versión con menos campos, agrega los nuevos
            existentes = {f[1] for f in con.execute("PRAGMA table_info(multas)")}
            for c in COLUMNAS:
                if c not in existentes:
                    con.execute(f"ALTER TABLE multas ADD COLUMN {c} {TIPO_SQLITE[tipos[c]]}")
            con.execute("CREATE INDEX IF NOT EXISTS ix_dni ON multas (dni)")
            con.commit()

    def ids_existentes(self):
        with closing(sqlite3.connect(self.ruta)) as con:
            return {f[0] for f in con.execute("SELECT id_multa FROM multas")}

    def insertar(self, df, fuente):
        d = _preparar(df, fuente)
        for c in COLUMNAS_FECHA:
            d[c] = d[c].astype("object").where(d[c].notna(), None)
            d[c] = d[c].map(lambda x: x.isoformat() if x is not None else None)
        d["fecha_carga"] = d["fecha_carga"].map(lambda x: x.isoformat(timespec="seconds"))
        with closing(sqlite3.connect(self.ruta)) as con:
            d.to_sql("multas", con, if_exists="append", index=False, chunksize=20_000)
            con.commit()
        return len(d)

    def consultar_dni(self, dni):
        with closing(sqlite3.connect(self.ruta)) as con:
            df = pd.read_sql_query(
                "SELECT * FROM multas WHERE dni = ? ORDER BY fecha_vencimiento",
                con, params=(dni,))
        return _a_fechas(df)

    def ultimos(self, n=10):
        with closing(sqlite3.connect(self.ruta)) as con:
            df = pd.read_sql_query(
                "SELECT * FROM multas ORDER BY fecha_carga DESC, rowid DESC LIMIT ?",
                con, params=(n,))
        return _a_fechas(df)

    def resumen(self):
        with closing(sqlite3.connect(self.ruta)) as con:
            total, ultima = con.execute(
                "SELECT COUNT(*), MAX(fecha_carga) FROM multas").fetchone()
        return total, ultima


# ======================================================================
# BIGQUERY (nube)
# ======================================================================
class BaseBigQuery:
    def __init__(self):
        from google.cloud import bigquery  # se importa aquí para no exigirlo en modo local
        self.bq = bigquery
        self.cliente = bigquery.Client(project=os.getenv("GCP_PROJECT") or None)
        dataset = os.getenv("BQ_DATASET", "multas_poc")
        self.tabla = f"{self.cliente.project}.{dataset}.multas"
        self.descripcion = f"BigQuery (nube) - {self.tabla}"

        self.esquema = [
            bigquery.SchemaField(c, logic.tipo_db(c),
                                 mode="REQUIRED" if c == "id_multa" else "NULLABLE")
            for c in logic.COLUMNAS_DATOS
        ] + [
            bigquery.SchemaField("fuente", "STRING"),
            bigquery.SchemaField("fecha_carga", "TIMESTAMP"),
        ]
        # Crea el dataset y la tabla si todavía no existen
        self.cliente.create_dataset(
            bigquery.Dataset(f"{self.cliente.project}.{dataset}"), exists_ok=True)
        tabla = self.cliente.create_table(bigquery.Table(self.tabla, schema=self.esquema),
                                          exists_ok=True)
        # Si la tabla ya existía con menos campos, agrega los que faltan
        presentes = {f.name for f in tabla.schema}
        faltantes = [f for f in self.esquema if f.name not in presentes]
        if faltantes:
            tabla.schema = list(tabla.schema) + [
                bigquery.SchemaField(f.name, f.field_type) for f in faltantes]
            self.cliente.update_table(tabla, ["schema"])

    def ids_existentes(self):
        filas = self.cliente.query(f"SELECT id_multa FROM `{self.tabla}`").result()
        return {f["id_multa"] for f in filas}

    def insertar(self, df, fuente):
        d = _preparar(df, fuente)
        config = self.bq.LoadJobConfig(
            schema=self.esquema,
            write_disposition=self.bq.WriteDisposition.WRITE_APPEND)
        # Carga por lote (load job): es la forma recomendada para archivos
        self.cliente.load_table_from_dataframe(d, self.tabla, job_config=config).result()
        return len(d)

    def consultar_dni(self, dni):
        config = self.bq.QueryJobConfig(query_parameters=[
            self.bq.ScalarQueryParameter("dni", "STRING", dni)])
        df = self.cliente.query(
            f"SELECT * FROM `{self.tabla}` WHERE dni = @dni ORDER BY fecha_vencimiento",
            job_config=config).to_dataframe()
        return _a_fechas(df)

    def ultimos(self, n=10):
        df = self.cliente.query(
            f"SELECT * FROM `{self.tabla}` ORDER BY fecha_carga DESC LIMIT {int(n)}"
        ).to_dataframe()
        return _a_fechas(df)

    def resumen(self):
        fila = list(self.cliente.query(
            f"SELECT COUNT(*) AS total, MAX(fecha_carga) AS ultima FROM `{self.tabla}`"
        ).result())[0]
        ultima = fila["ultima"].strftime("%Y-%m-%d %H:%M:%S") if fila["ultima"] else None
        return fila["total"], ultima


def crear_base():
    """Devuelve la base de datos según la variable BACKEND."""
    if os.getenv("BACKEND", "local").lower() == "bigquery":
        return BaseBigQuery()
    return BaseLocal()
