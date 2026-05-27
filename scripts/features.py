#!/usr/bin/env python3
"""
Capa de feature engineering para el modelo de clientes.
Fuente de datos: compliance.bbdd_clientes + compliance.bbdd_delitos

- Calcula variables derivadas desde registros de delitos y compliance
- Trata nulos
- Trata outliers por IQR
- Normaliza variables numéricas entre 0 y 1
"""

import logging
from typing import List

import numpy as np
import pandas as pd
import yaml
from pathlib import Path

log = logging.getLogger("features")

ROOT   = Path(__file__).parent.parent
PARAMS = yaml.safe_load((ROOT / "config" / "parameters.yaml").read_text())

# Columnas numéricas brutas que se normalizan
NUMERIC_COLS = [
    "delitos_count",
    "high_crimes",
    "medium_crimes",
    "crime_type_diversity",
    "active_crimes",
    "total_delitos",
]

# Columnas binarias (ya en 0/1, no se normalizan)
BINARY_COLS = [
    "con_info",
    "is_blocked",
    "under_review",
    "has_warning",
    "has_alerts",
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
    for col in BINARY_COLS:
        if col in df.columns:
            df[col] = df[col].fillna(0).astype(int)
    if "compliance_status" in df.columns:
        df["compliance_status"] = df["compliance_status"].fillna("UNKNOWN")
    return df


def _derived_variables(df: pd.DataFrame) -> pd.DataFrame:
    """Genera variables adicionales útiles para el scoring."""
    df = df.copy()

    # Proporción de delitos de alto riesgo sobre total
    df["high_crime_ratio"] = np.where(
        df["delitos_count"] > 0,
        df["high_crimes"] / df["delitos_count"],
        0.0,
    )

    # Score de severidad ponderada: high=1.0, medium=0.5, low=0.1
    df["crime_severity_score"] = (
        df["high_crimes"] * 1.0
        + df["medium_crimes"] * 0.5
        + df["low_crimes"] * 0.1
    )

    # Clientes con historial judicial activo (casos abiertos)
    df["has_active_crimes"] = (df["active_crimes"] > 0).astype(int)

    # Nivel de compliance como score numérico
    compliance_score_map = {
        "NORMAL":                   0.0,
        "WARNING":                  0.4,
        "UNDER_COMPLIANCE_REVIEW":  0.6,
        "UNDER_COMPLIANCE_REVIEW_2":0.65,
        "BLOCKED":                  0.8,
        "FULLY_BLOCKED":            1.0,
        "UNKNOWN":                  0.3,
    }
    df["compliance_score"] = df["compliance_status"].map(compliance_score_map).fillna(0.3)

    return df


def build_features(df_raw: pd.DataFrame) -> pd.DataFrame:
    log.info("Iniciando feature engineering — %d clientes", len(df_raw))

    df = _fill_nulls(df_raw)
    df = _derived_variables(df)

    factor = PARAMS["outliers"]["factor"]
    df = _cap_outliers(df, NUMERIC_COLS, factor=factor)
    df = _min_max_normalize(df, NUMERIC_COLS)

    # Normalizar también crime_severity_score y high_crime_ratio
    extra_num = ["crime_severity_score", "high_crime_ratio"]
    df = _cap_outliers(df, extra_num, factor=factor)
    df = _min_max_normalize(df, extra_num)

    log.info("Feature engineering completo — %d columnas generadas", len(df.columns))
    return df
