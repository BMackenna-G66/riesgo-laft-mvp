#!/usr/bin/env python3
"""
Score de riesgo jurisdiccional — Factor 2.
Combina tabla manual country_risk.csv con dispersión geográfica de destinos
para asignar score_jurisdiccion 0–1 por cliente.

Pesos internos:
  50% → Riesgo del país de origen del cliente (country_code en customer_v2)
  50% → Diversificación de países destino (proxy de riesgo de destinos)
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger("score_jurisdictions")

ROOT              = Path(__file__).parent.parent
COUNTRY_RISK_FILE = ROOT / "data" / "country_risk.csv"


def load_country_risk() -> pd.DataFrame:
    df = pd.read_csv(COUNTRY_RISK_FILE, dtype={"country_code": str})
    df["country_code"] = df["country_code"].str.strip().str.upper()
    log.info("Tabla de riesgo país cargada — %d países", len(df))
    return df


def _country_score(country_code: str, country_risk: pd.DataFrame) -> float:
    if not country_code or country_code in ("UNKNOWN", ""):
        return 0.5
    row = country_risk[country_risk["country_code"] == str(country_code).strip().upper()]
    if row.empty:
        log.debug("País '%s' no encontrado en tabla — score default 0.5", country_code)
        return 0.5
    return float(row["final_country_risk"].iloc[0])


def build_jurisdiction_scores(
    df_clients: pd.DataFrame,
    df_tx: pd.DataFrame = None,
) -> pd.DataFrame:
    """
    Calcula score_jurisdiccion por cliente combinando:
    - Riesgo del país de origen del cliente (country_code)
    - Diversificación geográfica de destinos (unique_destiny_countries_180d)

    Parameters
    ----------
    df_clients : DataFrame con al menos [customer_id, country_code]
                 y opcionalmente [unique_destiny_countries_180d]
    df_tx      : ignorado (mantenido por compatibilidad de interfaz)
    """
    log.info("Calculando scores de jurisdicción — %d clientes", len(df_clients))
    country_risk = load_country_risk()

    df = df_clients[["customer_id", "country_code"]].copy()
    df["country_code"] = df["country_code"].fillna("UNKNOWN").str.strip().str.upper()

    # Score país de origen
    df["score_pais_origen"] = df["country_code"].apply(
        lambda c: _country_score(c, country_risk)
    )

    # Diversificación de países destino
    if "unique_destiny_countries_180d" in df_clients.columns:
        max_dest = df_clients["unique_destiny_countries_180d"].max()
        df["dest_diversity_norm"] = (
            df_clients["unique_destiny_countries_180d"].fillna(0) / max(max_dest, 1)
        )
    else:
        df["dest_diversity_norm"] = 0.0

    # Score final jurisdicción = 50% origen + 50% dispersión destino
    df["score_jurisdiccion"] = (
        0.50 * df["score_pais_origen"] +
        0.50 * df["dest_diversity_norm"]
    ).clip(0, 1).round(4)

    log.info(
        "Score jurisdicción — min=%.4f, max=%.4f, media=%.4f",
        df["score_jurisdiccion"].min(),
        df["score_jurisdiccion"].max(),
        df["score_jurisdiccion"].mean(),
    )

    return df[["customer_id", "score_pais_origen", "dest_diversity_norm", "score_jurisdiccion"]]
