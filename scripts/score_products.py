#!/usr/bin/env python3
"""
Score de riesgo de productos — Factor 3.
Scoring ponderado / juicio experto desde config/products_risk.yaml.
Para MVP: un score único de portfolio de productos (sin desglose por cliente).
"""

import logging
from pathlib import Path
from typing import Optional

import pandas as pd
import yaml

log = logging.getLogger("score_products")

ROOT = Path(__file__).parent.parent
PRODUCTS_CONFIG = ROOT / "config" / "products_risk.yaml"


def compute_portfolio_product_score() -> float:
    """Calcula score único del portfolio de productos de la empresa."""
    cfg = yaml.safe_load(PRODUCTS_CONFIG.read_text())
    products = cfg["products"]

    total_weight = sum(p["ponderacion"] for p in products)
    if total_weight == 0:
        log.warning("Ponderaciones de productos suman 0 — score default 0.5")
        return 0.5

    weighted_score = sum(p["score_experto"] * p["ponderacion"] for p in products)
    score = round(weighted_score / total_weight, 4)
    log.info("Score portfolio productos = %.4f (pesos totales=%.2f)", score, total_weight)
    return score


def build_products_df() -> pd.DataFrame:
    """Retorna DataFrame con detalle de scoring por producto."""
    cfg = yaml.safe_load(PRODUCTS_CONFIG.read_text())
    rows = []
    for p in cfg["products"]:
        rows.append({
            "producto": p["producto"],
            "tipo": p.get("tipo", ""),
            "es_transaccional": p.get("es_transaccional", False),
            "score_experto": p["score_experto"],
            "ponderacion": p["ponderacion"],
            "score_ponderado": round(p["score_experto"] * p["ponderacion"], 4),
        })
    df = pd.DataFrame(rows)
    total = df["ponderacion"].sum()
    df["score_normalizado"] = (df["score_ponderado"] / total).round(4) if total > 0 else 0.0
    return df


def assign_product_score_to_clients(df_clients: pd.DataFrame) -> pd.DataFrame:
    """
    Para MVP: el score de producto es el mismo para todos los clientes
    (no hay desglose por producto usado por cliente).
    Se puede extender cuando exista tabla cliente–producto.
    """
    portfolio_score = compute_portfolio_product_score()
    df = df_clients[["customer_id"]].copy()
    df["score_producto"] = portfolio_score
    log.info("Score producto asignado a %d clientes (portfolio único)", len(df))
    return df
