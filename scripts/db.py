#!/usr/bin/env python3
"""
Conexión a Redshift con autenticación IAM.

Cluster:  compliance-redshift-cluster.cszw4nrem7jk.us-east-1.redshift.amazonaws.com
Region:   us-east-1
Auth:     AWS IAM (sin contraseñas estáticas en código)

Credenciales requeridas en .env:
    AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
    REDSHIFT_CLUSTER_ID, REDSHIFT_DATABASE, REDSHIFT_DB_USER
    REDSHIFT_HOST, REDSHIFT_PORT, AWS_REGION
"""

import logging
import os
from pathlib import Path

import pandas as pd
import redshift_connector
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

log = logging.getLogger("db")

# ── Constantes del cluster (públicas, no secretos) ────────────────────────
CLUSTER_ENDPOINT = "compliance-redshift-cluster.cszw4nrem7jk.us-east-1.redshift.amazonaws.com"
CLUSTER_ID       = "compliance-redshift-cluster"
CLUSTER_REGION   = "us-east-1"
CLUSTER_PORT     = 5439


def get_connection() -> redshift_connector.Connection:
    """
    Abre conexión a Redshift usando autenticación IAM.
    Las credenciales AWS se leen desde variables de entorno (nunca hardcodeadas).
    """
    host     = os.getenv("REDSHIFT_HOST",       CLUSTER_ENDPOINT)
    port     = int(os.getenv("REDSHIFT_PORT",   CLUSTER_PORT))
    database = os.environ["REDSHIFT_DATABASE"]
    region   = os.getenv("AWS_REGION",          CLUSTER_REGION)
    cluster  = os.getenv("REDSHIFT_CLUSTER_ID", CLUSTER_ID)
    db_user  = os.environ["REDSHIFT_DB_USER"]

    access_key = os.environ.get("AWS_ACCESS_KEY_ID")
    secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")

    if not access_key or not secret_key:
        raise EnvironmentError(
            "Faltan AWS_ACCESS_KEY_ID o AWS_SECRET_ACCESS_KEY en el archivo .env"
        )

    log.info("Conectando a Redshift [%s/%s] con IAM user=%s …", host, database, db_user)

    conn = redshift_connector.connect(
        host=host,
        port=port,
        database=database,
        db_user=db_user,
        cluster_identifier=cluster,
        region=region,
        access_key_id=access_key,
        secret_access_key=secret_key,
        iam=True,
        timeout=60,
        tcp_keepalive=True,
    )
    conn.autocommit = True
    log.info("Conexión establecida.")
    return conn


def query_to_df(sql: str, conn=None) -> pd.DataFrame:
    """Ejecuta SQL y retorna DataFrame. Abre y cierra conexión si no se pasa una."""
    close_after = conn is None
    if close_after:
        conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        cols = [d[0] for d in cursor.description]
        rows = cursor.fetchall()
        df = pd.DataFrame(rows, columns=cols)
        log.info("Query OK — %d filas retornadas", len(df))
        return df
    finally:
        if close_after:
            conn.close()


def load_sql(filename: str) -> str:
    """Carga un archivo .sql y sustituye el prefijo de base de datos."""
    queries_dir = Path(__file__).parent.parent / "queries"
    sql = (queries_dir / filename).read_text(encoding="utf-8")
    return _apply_db_prefix(sql)


def _apply_db_prefix(sql: str) -> str:
    """
    Sustituye "db_prod" en las queries por el valor de REDSHIFT_DB_PREFIX del .env.
    Permite usar las mismas queries en producción (db_prod) y en el cluster
    de compliance (dev) sin modificar los archivos SQL.
    """
    db_prefix = os.getenv("REDSHIFT_DB_PREFIX", "db_prod")
    if db_prefix != "db_prod":
        sql = sql.replace('"db_prod"', f'"{db_prefix}"')
        log.debug("DB prefix sustituido: db_prod → %s", db_prefix)
    return sql
