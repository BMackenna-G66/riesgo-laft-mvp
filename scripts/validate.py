#!/usr/bin/env python3
"""
Validaciones del pipeline — registra errores y advertencias en log.
Retorna True si el resultado es válido para exportar, False si hay errores críticos.
"""

import logging
from typing import Tuple

import pandas as pd

log = logging.getLogger("validate")


def validate_pipeline(
    df_raw: pd.DataFrame,
    df_features: pd.DataFrame,
    df_clients_results: pd.DataFrame,
    df_final: pd.DataFrame,
) -> Tuple[bool, list]:
    errors = []
    warnings = []

    # 1. Cantidad de clientes procesados
    n_raw = len(df_raw)
    n_final = len(df_final)
    if n_raw == 0:
        errors.append("CRÍTICO: No se extrajeron clientes desde Redshift.")
    elif n_final < n_raw * 0.80:
        warnings.append(
            f"Se procesaron {n_final} de {n_raw} clientes ({n_final/n_raw:.0%}). "
            "Posible pérdida de datos en joins."
        )

    # 2. Duplicados en customer_id
    dupes = df_final["customer_id"].duplicated().sum()
    if dupes > 0:
        errors.append(f"CRÍTICO: {dupes} customer_id duplicados en df_final.")

    # 3. Nulos por variable en features
    numeric_cols = [c for c in df_features.columns if c.endswith("_norm")]
    for col in numeric_cols:
        null_pct = df_features[col].isna().mean()
        if null_pct > 0.20:
            warnings.append(f"'{col}': {null_pct:.0%} de valores nulos post-features.")

    # 4. Distribución de clusters (ningún cluster debe tener más del 90% de clientes)
    if "cluster_label" in df_clients_results.columns:
        dist = df_clients_results["cluster_label"].value_counts(normalize=True)
        for label, pct in dist.items():
            if pct > 0.90:
                warnings.append(
                    f"Cluster '{label}' concentra {pct:.0%} de clientes — revisar calidad del clustering."
                )

    # 5. score_final entre 0 y 1
    out_of_range = ((df_final["score_final"] < 0) | (df_final["score_final"] > 1)).sum()
    if out_of_range > 0:
        errors.append(f"CRÍTICO: {out_of_range} clientes con score_final fuera de [0,1].")

    # 6. Todos los clientes tienen nivel de riesgo
    missing_nivel = df_final["nivel_riesgo_final"].isna().sum()
    if missing_nivel > 0:
        errors.append(f"CRÍTICO: {missing_nivel} clientes sin nivel_riesgo_final.")

    # 7. Distribución de niveles de riesgo — aviso si todo es Bajo o todo es Alto
    nivel_dist = df_final["nivel_riesgo_final"].value_counts(normalize=True).to_dict()
    for nivel, pct in nivel_dist.items():
        if pct > 0.95:
            warnings.append(
                f"Nivel '{nivel}' representa el {pct:.0%} del total. "
                "Revisar parámetros del modelo."
            )

    # Loguear resultados
    all_issues = errors + warnings
    if errors:
        for e in errors:
            log.error(e)
    if warnings:
        for w in warnings:
            log.warning(w)
    if not all_issues:
        log.info("Validaciones OK — sin errores ni advertencias.")

    is_valid = len(errors) == 0

    log.info(
        "Validación completada — clientes=%d, score_final rango=[%.4f, %.4f], distribución=%s",
        n_final,
        df_final["score_final"].min(),
        df_final["score_final"].max(),
        nivel_dist,
    )

    return is_valid, all_issues
