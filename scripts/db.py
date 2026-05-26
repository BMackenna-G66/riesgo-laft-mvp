#!/usr/bin/env python3
"""
Helper de conexión a Redshift.
Carga credenciales desde .env y expone query_to_df().
"""

import logging
import os
from pathlib import Path
from typing import Optional

import pandas as pd
import psycopg2
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

log = logging.getLogger("db")


def get_connection() -> psycopg2.extensions.connection:
    conn = psycopg2.connect(
        host=os.environ["REDSHIFT_HOST"],
        port=int(os.getenv("REDSHIFT_PORT", 5439)),
        database=os.environ["REDSHIFT_DATABASE"],
        user=os.environ["REDSHIFT_USER"],
        password=os.environ["REDSHIFT_PASSWORD"],
        connect_timeout=30,
        options="-c statement_timeout=300000",
    )
    conn.autocommit = True
    return conn


def query_to_df(sql: str, conn: Optional[psycopg2.extensions.connection] = None) -> pd.DataFrame:
    close_after = conn is None
    if close_after:
        conn = get_connection()
    try:
        df = pd.read_sql(sql, conn)
        log.info("Query ejecutada — %d filas retornadas", len(df))
        return df
    finally:
        if close_after:
            conn.close()


def load_sql(filename: str) -> str:
    queries_dir = Path(__file__).parent.parent / "queries"
    return (queries_dir / filename).read_text(encoding="utf-8")
