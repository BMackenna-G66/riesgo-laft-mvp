#!/usr/bin/env python3
"""
Score final consolidado — combina los 4 factores.

score_final = score_cliente * peso_cliente
            + score_jurisdiccion * peso_jurisdiccion
            + score_producto * peso_producto
            + score_canal * peso_canal

Pesos configurables en config/parameters.yaml.
"""

import logging
from datetime import date
from pathlib import Path

import pandas as pd
import yaml

log = logging.getLogger("score_final")

ROOT = Path(__file__).parent.parent
PARAMS = yaml.safe_load((ROOT / "config" / "parameters.yaml").read_text())


def _nivel_from_score(score: float) -> str:
    levels = PARAMS["risk_levels"]
    if score <= levels["bajo"]["max"]:
        return "Bajo"
    elif score <= levels["medio"]["max"]:
        return "Medio"
    return "Alto"


def build_final_score(
    df_clients_results: pd.DataFrame,
    df_jurisdiction: pd.DataFrame,
    df_products: pd.DataFrame,
    df_channels: pd.DataFrame,
) -> pd.DataFrame:
    """
    Consolida los 4 scores en un DataFrame final por cliente.

    df_clients_results:  customer_id, score_cliente, nivel_riesgo_cliente, principales_features
    df_jurisdiction:     customer_id, score_jurisdiccion
    df_products:         customer_id, score_producto
    df_channels:         customer_id, score_canal
    """
    weights = PARAMS["weights"]
    run_date = str(date.today())
    version = PARAMS["model"]["version"]

    log.info(
        "Calculando score final — pesos: cliente=%.0f%% jurisdiccion=%.0f%% producto=%.0f%% canal=%.0f%%",
        weights["clientes"] * 100,
        weights["jurisdicciones"] * 100,
        weights["productos"] * 100,
        weights["canales"] * 100,
    )

    df = df_clients_results[["customer_id", "score_cliente", "nivel_riesgo_cliente", "principales_features"]].copy()

    df = df.merge(
        df_jurisdiction[["customer_id", "score_jurisdiccion"]],
        on="customer_id", how="left",
    )
    df = df.merge(
        df_products[["customer_id", "score_producto"]],
        on="customer_id", how="left",
    )
    df = df.merge(
        df_channels[["customer_id", "score_canal"]],
        on="customer_id", how="left",
    )

    df["score_jurisdiccion"] = df["score_jurisdiccion"].fillna(0.5)
    df["score_producto"] = df["score_producto"].fillna(0.5)
    df["score_canal"] = df["score_canal"].fillna(0.5)

    df["score_final"] = (
        df["score_cliente"] * weights["clientes"] +
        df["score_jurisdiccion"] * weights["jurisdicciones"] +
        df["score_producto"] * weights["productos"] +
        df["score_canal"] * weights["canales"]
    ).clip(0, 1).round(4)

    df["nivel_riesgo_final"] = df["score_final"].apply(_nivel_from_score)
    df["fecha_calculo"] = run_date
    df["version_modelo"] = version

    # Drivers principales: las 2 variables con mayor contribución al score final
    df["principales_drivers"] = df.apply(_compute_drivers, axis=1, weights=weights)

    dist = df["nivel_riesgo_final"].value_counts().to_dict()
    log.info("Distribución score final: %s", dist)
    log.info(
        "Score final — min=%.4f, max=%.4f, media=%.4f",
        df["score_final"].min(),
        df["score_final"].max(),
        df["score_final"].mean(),
    )

    cols = [
        "customer_id",
        "score_cliente",
        "score_jurisdiccion",
        "score_producto",
        "score_canal",
        "score_final",
        "nivel_riesgo_final",
        "nivel_riesgo_cliente",
        "principales_features",
        "principales_drivers",
        "fecha_calculo",
        "version_modelo",
    ]
    return df[cols]


def _compute_drivers(row: pd.Series, weights: dict) -> str:
    contributions = {
        "cliente": row["score_cliente"] * weights["clientes"],
        "jurisdiccion": row["score_jurisdiccion"] * weights["jurisdicciones"],
        "producto": row["score_producto"] * weights["productos"],
        "canal": row["score_canal"] * weights["canales"],
    }
    top2 = sorted(contributions, key=contributions.get, reverse=True)[:2]
    return ", ".join(top2)
