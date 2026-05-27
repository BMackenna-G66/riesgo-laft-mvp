#!/usr/bin/env python3
"""
Score de riesgo jurisdiccional — Factor 2.

Fuente: campo `grupo` de compliance.bbdd_clientes.

El campo `grupo` (1–5) es la segmentación interna por perfil de riesgo de
jurisdicción del cliente. Se mapea a un score 0–1:
  1 → 0.10 (muy bajo)
  2 → 0.30 (bajo)
  3 → 0.50 (medio)
  4 → 0.70 (alto)
  5 → 0.90 (muy alto)
"""

import logging

import pandas as pd

log = logging.getLogger("score_jurisdictions")

# Mapa grupo → score de jurisdicción (0.0–1.0)
GRUPO_RISK_MAP = {
    1: 0.10,
    2: 0.30,
    3: 0.50,
    4: 0.70,
    5: 0.90,
}

DEFAULT_RISK = 0.50   # Para grupos no mapeados


def build_jurisdiction_scores(df_raw: pd.DataFrame, *args, **kwargs) -> pd.DataFrame:
    """
    Calcula score_jurisdiccion por cliente usando el campo `grupo`.

    Parameters
    ----------
    df_raw : DataFrame con al menos las columnas [customer_id, grupo]

    Returns
    -------
    DataFrame con columnas [customer_id, grupo, score_jurisdiccion]
    """
    log.info("Calculando scores de jurisdicción — %d clientes", len(df_raw))

    if "grupo" not in df_raw.columns:
        log.warning("Columna 'grupo' no encontrada — asignando score_jurisdiccion=0.50")
        df = df_raw[["customer_id"]].copy()
        df["score_jurisdiccion"] = DEFAULT_RISK
        return df

    df = df_raw[["customer_id", "grupo"]].copy()
    df["grupo"] = pd.to_numeric(df["grupo"], errors="coerce").fillna(3).astype(int)
    df["score_jurisdiccion"] = df["grupo"].map(GRUPO_RISK_MAP).fillna(DEFAULT_RISK)

    # Estadísticas de distribución
    dist = df.groupby("score_jurisdiccion")["customer_id"].count()
    for score, count in dist.items():
        log.info("  Jurisdicción score=%.2f → %d clientes (%.1f%%)",
                 score, count, 100 * count / len(df))

    log.info(
        "Score jurisdicción — min=%.4f, max=%.4f, media=%.4f",
        df["score_jurisdiccion"].min(),
        df["score_jurisdiccion"].max(),
        df["score_jurisdiccion"].mean(),
    )
    return df[["customer_id", "score_jurisdiccion"]]
