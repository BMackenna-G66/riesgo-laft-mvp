#!/usr/bin/env python3
"""
Score de riesgo de canales — Factor 4.
Scoring ponderado / juicio experto desde config/channels_risk.yaml.
Para MVP: un score único de portfolio de canales (sin desglose por cliente).
"""

import logging
from pathlib import Path

import pandas as pd
import yaml

log = logging.getLogger("score_channels")

ROOT = Path(__file__).parent.parent
CHANNELS_CONFIG = ROOT / "config" / "channels_risk.yaml"


def compute_portfolio_channel_score() -> float:
    """Calcula score único del portfolio de canales de la empresa."""
    cfg = yaml.safe_load(CHANNELS_CONFIG.read_text())
    channels = cfg["channels"]

    total_weight = sum(c["ponderacion"] for c in channels)
    if total_weight == 0:
        log.warning("Ponderaciones de canales suman 0 — score default 0.5")
        return 0.5

    weighted_score = sum(c["score_experto"] * c["ponderacion"] for c in channels)
    score = round(weighted_score / total_weight, 4)
    log.info("Score portfolio canales = %.4f (pesos totales=%.2f)", score, total_weight)
    return score


def build_channels_df() -> pd.DataFrame:
    """Retorna DataFrame con detalle de scoring por canal."""
    cfg = yaml.safe_load(CHANNELS_CONFIG.read_text())
    rows = []
    for c in cfg["channels"]:
        rows.append({
            "canal": c["canal"],
            "uso": c.get("uso", ""),
            "origen_transaccion": c.get("origen_transaccion", ""),
            "alcance_geografico": c.get("alcance_geografico", ""),
            "permite_pago_terceros": c.get("permite_pago_terceros", False),
            "doble_factor": c.get("doble_factor", False),
            "score_experto": c["score_experto"],
            "ponderacion": c["ponderacion"],
            "score_ponderado": round(c["score_experto"] * c["ponderacion"], 4),
        })
    df = pd.DataFrame(rows)
    total = df["ponderacion"].sum()
    df["score_normalizado"] = (df["score_ponderado"] / total).round(4) if total > 0 else 0.0
    return df


def assign_channel_score_to_clients(df_clients: pd.DataFrame) -> pd.DataFrame:
    """
    Para MVP: el score de canal es el mismo para todos los clientes.
    Se puede extender cuando exista tabla cliente–canal.
    """
    portfolio_score = compute_portfolio_channel_score()
    df = df_clients[["customer_id"]].copy()
    df["score_canal"] = portfolio_score
    log.info("Score canal asignado a %d clientes (portfolio único)", len(df))
    return df
