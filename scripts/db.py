#!/usr/bin/env python3
"""
Conexión a Redshift via Redshift Data API (HTTPS).

Usa la Redshift Data API en lugar de TCP directo al puerto 5439, por lo que
no depende de reglas de Security Group en la VPC.

Cluster:  compliance-redshift-cluster
Region:   us-east-1
Auth:     AWS IAM (sin contraseñas estáticas en código)

Credenciales requeridas en .env:
    AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION
    REDSHIFT_CLUSTER_ID, REDSHIFT_DATABASE, REDSHIFT_DB_USER
"""

import logging
import os
import time
from pathlib import Path

import boto3
import pandas as pd
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

log = logging.getLogger("db")

# ── Constantes del cluster (públicas, no secretos) ────────────────────────
CLUSTER_ID     = "compliance-redshift-cluster"
CLUSTER_REGION = "us-east-1"

# Tiempo máximo de espera por query (segundos)
QUERY_TIMEOUT  = 300
POLL_INTERVAL  = 2   # segundos entre polls


def _client():
    """Crea cliente boto3 para Redshift Data API."""
    region     = os.getenv("AWS_REGION", CLUSTER_REGION)
    access_key = os.environ.get("AWS_ACCESS_KEY_ID")
    secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")

    if not access_key or not secret_key:
        raise EnvironmentError(
            "Faltan AWS_ACCESS_KEY_ID o AWS_SECRET_ACCESS_KEY en el archivo .env"
        )

    return boto3.client(
        "redshift-data",
        region_name=region,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )


def query_to_df(sql: str, conn=None) -> pd.DataFrame:
    """
    Ejecuta SQL via Redshift Data API y retorna DataFrame.
    El parámetro `conn` se acepta por compatibilidad pero se ignora
    (la Data API no usa conexiones persistentes).
    """
    database = os.environ["REDSHIFT_DATABASE"]
    cluster  = os.getenv("REDSHIFT_CLUSTER_ID", CLUSTER_ID)
    db_user  = os.environ["REDSHIFT_DB_USER"]

    client = _client()

    # Límite de filas configurable (solo para dev/testing; 0 = sin límite)
    max_rows = int(os.getenv("REDSHIFT_MAX_ROWS", 0))
    if max_rows and "LIMIT" not in sql.upper().split("--")[0][-200:]:
        sql = sql.rstrip().rstrip(";") + f"\nLIMIT {max_rows}"
        log.info("REDSHIFT_MAX_ROWS=%d aplicado a la query", max_rows)

    log.info("Enviando query via Data API [%s/%s] …", cluster, database)

    # Enviar statement
    resp = client.execute_statement(
        ClusterIdentifier=cluster,
        Database=database,
        DbUser=db_user,
        Sql=sql,
    )
    stmt_id = resp["Id"]
    log.debug("Statement ID: %s", stmt_id)

    # Polling hasta que termine
    deadline = time.time() + QUERY_TIMEOUT
    while time.time() < deadline:
        desc = client.describe_statement(Id=stmt_id)
        status = desc["Status"]
        if status == "FINISHED":
            break
        if status in ("FAILED", "ABORTED"):
            err = desc.get("Error", "sin detalle")
            raise RuntimeError(f"Query fallida [{status}]: {err}\nSQL: {sql[:300]}")
        time.sleep(POLL_INTERVAL)
    else:
        raise TimeoutError(
            f"Query superó {QUERY_TIMEOUT}s sin respuesta. Statement ID: {stmt_id}"
        )

    # Sin resultados (DDL, INSERT, etc.)
    if not desc.get("HasResultSet"):
        log.info("Query OK — sin filas (DML/DDL)")
        return pd.DataFrame()

    # Recuperar resultados (paginado con reintentos para errores de red)
    total_rows = desc.get("ResultRows", 0)
    log.info("Descargando %s filas…", f"{total_rows:,}" if total_rows else "?")

    rows_all  = []
    col_meta  = None
    kwargs    = {"Id": stmt_id}
    page_num  = 0
    MAX_RETRY = 5     # reintentos por error de red

    while True:
        # Llamada con reintentos exponenciales
        for attempt in range(MAX_RETRY):
            try:
                page = client.get_statement_result(**kwargs)
                break
            except Exception as net_err:
                if attempt == MAX_RETRY - 1:
                    raise
                wait = 2 ** attempt
                log.warning("Error de red en página %d (intento %d/%d): %s — reintentando en %ds",
                            page_num, attempt + 1, MAX_RETRY, net_err, wait)
                time.sleep(wait)
                client = _client()   # nuevo cliente boto3

        if col_meta is None:
            col_meta = page["ColumnMetadata"]

        for row in page.get("Records", []):
            parsed = []
            for cell in row:
                val = next(iter(cell.values()))
                parsed.append(None if "isNull" in cell and cell.get("isNull") else val)
            rows_all.append(parsed)

        page_num += 1
        if page_num % 200 == 0:
            log.info("  … %d filas descargadas", len(rows_all))

        next_token = page.get("NextToken")
        if not next_token:
            break
        kwargs["NextToken"] = next_token

    cols = [c["name"] for c in col_meta] if col_meta else []
    df   = pd.DataFrame(rows_all, columns=cols)

    # Convertir tipos numéricos (la Data API devuelve todo como string en algunas versiones)
    for meta in (col_meta or []):
        col  = meta["name"]
        kind = meta.get("typeName", "")
        if col not in df.columns:
            continue
        if kind in ("int4", "int8", "int2", "float4", "float8", "numeric"):
            df[col] = pd.to_numeric(df[col], errors="coerce")

    log.info("Query OK — %d filas, %d columnas", len(df), len(df.columns))
    return df


def load_sql(filename: str) -> str:
    """Carga un archivo .sql y sustituye el prefijo de base de datos."""
    queries_dir = Path(__file__).parent.parent / "queries"
    sql = (queries_dir / filename).read_text(encoding="utf-8")
    return _apply_db_prefix(sql)


def _apply_db_prefix(sql: str) -> str:
    """
    Sustituye "db_prod" en las queries por el valor de REDSHIFT_DB_PREFIX del .env.
    Permite usar las mismas queries en producción (db_prod) y en otros entornos
    sin modificar los archivos SQL.
    Con REDSHIFT_DB_PREFIX=db_prod no hay ninguna sustitución (comportamiento default).
    """
    db_prefix = os.getenv("REDSHIFT_DB_PREFIX", "db_prod")
    if db_prefix != "db_prod":
        sql = sql.replace('"db_prod"', f'"{db_prefix}"')
        log.debug("DB prefix sustituido: db_prod → %s", db_prefix)
    return sql


# ── Compatibilidad retroactiva ─────────────────────────────────────────────
def get_connection():
    """
    DEPRECATED. Mantenido por compatibilidad.
    La Data API no usa conexiones persistentes; retorna None.
    """
    log.warning(
        "get_connection() está obsoleto con la Data API. "
        "Usa query_to_df(sql) directamente."
    )
    return None
