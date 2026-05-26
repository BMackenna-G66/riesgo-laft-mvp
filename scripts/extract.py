#!/usr/bin/env python3
"""
Capa de extracción: ejecuta las queries SQL base contra Redshift
y retorna DataFrames staging listos para feature engineering.
"""

import logging
from typing import Tuple

import pandas as pd

from db import get_connection, load_sql, query_to_df

log = logging.getLogger("extract")


def extract_all() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Ejecuta las 5 queries y retorna los DataFrames staging."""
    log.info("Abriendo conexión a Redshift…")
    conn = get_connection()

    try:
        log.info("Extrayendo Query 1 — clientes + KYC + empresa…")
        df_clientes = query_to_df(load_sql("01_clientes_kyc.sql"), conn)

        log.info("Extrayendo Query 2 — métricas cash_call 30/90/180d…")
        df_cash = query_to_df(load_sql("02_cash_call_metricas.sql"), conn)

        log.info("Extrayendo Query 3 — beneficiarios y dispersión…")
        df_beneficiarios = query_to_df(load_sql("03_beneficiarios.sql"), conn)

        log.info("Extrayendo Query 4 — transacciones destino/beneficiario…")
        df_tx = query_to_df(load_sql("04_transacciones.sql"), conn)

        log.info("Extrayendo Query 5 — consolidado principal…")
        df_consolidado = query_to_df(load_sql("05_consolidado.sql"), conn)

    finally:
        conn.close()
        log.info("Conexión cerrada.")

    log.info(
        "Extracción completa — clientes=%d, cash=%d, benef=%d, tx=%d, consolidado=%d",
        len(df_clientes), len(df_cash), len(df_beneficiarios), len(df_tx), len(df_consolidado),
    )
    return df_clientes, df_cash, df_beneficiarios, df_tx, df_consolidado


def extract_consolidado() -> pd.DataFrame:
    """Extrae solo la query consolidada (uso rápido en pipeline MVP)."""
    log.info("Extrayendo query consolidada…")
    return query_to_df(load_sql("05_consolidado.sql"))
