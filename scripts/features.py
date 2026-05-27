#!/usr/bin/env python3
"""
Capa de feature engineering para el modelo de clientes.
Fuente de datos: db_prod.customer.customer_v2 + db_prod.treasury.cash_call
                 + db_prod.transaction.transaction (via 05_consolidado.sql)

- Calcula variables derivadas (antigüedad, ratio beneficiarios, etc.)
- Trata nulos (rellena con 0 en numéricas, 'UNKNOWN' en categóricas)
- Trata outliers por IQR (factor configurable en parameters.yaml)
- Normaliza variables numéricas entre 0 y 1
"""

import logging
from datetime import date
from typing import List

import numpy as np
import pandas as pd
import yaml
from pathlib import Path

log = logging.getLogger("features")

ROOT   = Path(__file__).parent.parent
PARAMS = yaml.safe_load((ROOT / "config" / "parameters.yaml").read_text())

# Columnas numéricas brutas provenientes de la query consolidada
NUMERIC_COLS = [
    "trx_180d",
    "volume_usd_180d",
    "avg_ticket_usd_180d",
    "max_ticket_usd_180d",
    "rejection_rate_180d",
    "unique_external_funders_180d",
    "unique_beneficiaries_180d",
    "unique_destiny_countries_180d",
    "unique_currencies_180d",
    "unique_payment_methods_180d",
]


def _cap_outliers(df: pd.DataFrame, cols: List[str], factor: float = 3.0) -> pd.DataFrame:
    df = df.copy()
    for col in cols:
        if col not in df.columns:
            continue
        q1 = df[col].quantile(0.25)
        q3 = df[col].quantile(0.75)
        iqr = q3 - q1
        upper = q3 + factor * iqr
        capped = (df[col] > upper).sum()
        if capped > 0:
            log.info("Outliers capados en '%s': %d filas (cap=%.2f)", col, capped, upper)
        df[col] = df[col].clip(upper=upper)
    return df


def _min_max_normalize(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    df = df.copy()
    for col in cols:
        if col not in df.columns:
            log.warning("Columna '%s' no encontrada — se omite normalización", col)
            continue
        col_min = df[col].min()
        col_max = df[col].max()
        norm_col = f"{col}_norm"
        if col_max == col_min:
            df[norm_col] = 0.0
        else:
            df[norm_col] = (df[col] - col_min) / (col_max - col_min)
    return df


def _fill_nulls(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in NUMERIC_COLS:
        if col in df.columns:
            null_count = df[col].isna().sum()
            if null_count > 0:
                log.info("Nulos en '%s': %d — rellenados con 0", col, null_count)
            df[col] = df[col].fillna(0)
    for col in ["compliance_status", "country_code"]:
        if col in df.columns:
            df[col] = df[col].fillna("UNKNOWN")
    return df


def _derived_variables(df: pd.DataFrame) -> pd.DataFrame:
    """Genera variables adicionales para el modelo."""
    df = df.copy()
    today = date.today()

    # Antigüedad del cliente en días
    if "customer_created_at" in df.columns:
        df["customer_created_at"] = pd.to_datetime(df["customer_created_at"], errors="coerce")
        df["customer_age_days"] = (
            pd.Timestamp(today) - df["customer_created_at"]
        ).dt.days.fillna(0).clip(lower=0)
    else:
        df["customer_age_days"] = 0

    # Días desde última operación
    if "last_operation_date" in df.columns:
        df["last_operation_date"] = pd.to_datetime(df["last_operation_date"], errors="coerce")
        df["days_since_last_op"] = (
            pd.Timestamp(today) - df["last_operation_date"]
        ).dt.days.fillna(999)
    else:
        df["days_since_last_op"] = 999

    # Ratio beneficiarios / transacciones (diversificación de destinos)
    df["beneficiary_per_trx"] = np.where(
        df["trx_180d"] > 0,
        df.get("unique_beneficiaries_180d", pd.Series(0, index=df.index)) / df["trx_180d"],
        0.0,
    )

    # Indicador cliente empresa
    if "is_company" in df.columns:
        df["es_empresa"] = df["is_company"].fillna(False).astype(int)
    else:
        df["es_empresa"] = 0

    # Compliance risk flag: clientes con nivel de riesgo alto o medio = mayor exposición
    if "compliance_status" in df.columns:
        df["compliance_risk_flag"] = df["compliance_status"].str.upper().isin(
            ["ALTO", "MEDIO", "HIGH", "MEDIUM"]
        ).astype(int)
    else:
        df["compliance_risk_flag"] = 0

    return df


def build_features(df_raw: pd.DataFrame) -> pd.DataFrame:
    log.info("Iniciando feature engineering — %d clientes", len(df_raw))

    df = _fill_nulls(df_raw)
    df = _derived_variables(df)

    factor = PARAMS["outliers"]["factor"]
    df = _cap_outliers(df, NUMERIC_COLS, factor=factor)
    df = _min_max_normalize(df, NUMERIC_COLS)

    # Normalizar también variables derivadas numéricas
    derived_num = ["customer_age_days", "days_since_last_op", "beneficiary_per_trx"]
    df = _cap_outliers(df, derived_num, factor=factor)
    df = _min_max_normalize(df, derived_num)

    log.info("Feature engineering completo — %d columnas generadas", len(df.columns))
    return df
