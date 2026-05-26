#!/usr/bin/env python3
"""
Modelo de segmentación de clientes — Factor 1.
- KMeans k=3 sobre variables normalizadas
- Asigna cluster a cada cliente
- Mapea cluster → nivel de riesgo por score compuesto de centroide
- Calcula score_cliente 0–1 como distancia ponderada al centroide de alto riesgo
- Guarda centroides y explicación de cada segmento
"""

import json
import logging
from datetime import date
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import pandas as pd
import yaml
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

log = logging.getLogger("model_clients")

ROOT = Path(__file__).parent.parent
PARAMS = yaml.safe_load((ROOT / "config" / "parameters.yaml").read_text())
MODELS_DIR = ROOT / "outputs"


def _get_feature_matrix(df: pd.DataFrame) -> Tuple[pd.DataFrame, list]:
    feature_cols = PARAMS["feature_columns"]
    available = [c for c in feature_cols if c in df.columns]
    missing = [c for c in feature_cols if c not in df.columns]
    if missing:
        log.warning("Features faltantes (se omiten): %s", missing)
    return df[available].fillna(0), available


def _composite_score(centroid: np.ndarray) -> float:
    """Score compuesto de un centroide = promedio simple de sus componentes."""
    return float(np.mean(centroid))


def _map_clusters_to_risk(centroids: np.ndarray) -> Dict[int, str]:
    """Ordena clusters por score compuesto ascendente → Bajo, Medio, Alto."""
    scores = {i: _composite_score(c) for i, c in enumerate(centroids)}
    ranked = sorted(scores, key=scores.get)
    mapping = {ranked[0]: "Bajo", ranked[1]: "Medio", ranked[2]: "Alto"}
    log.info(
        "Mapeo clusters: %s | Scores: %s",
        mapping,
        {i: round(s, 4) for i, s in scores.items()},
    )
    return mapping


def _score_from_cluster(cluster_label: str, dist_to_high_risk: float, max_dist: float) -> float:
    """
    Score 0-1 basado en cluster + distancia al centroide de alto riesgo.
    Clientes Alto → score base 0.67–1.0; Medio → 0.34–0.66; Bajo → 0.0–0.33.
    """
    if max_dist == 0:
        base_map = {"Bajo": 0.15, "Medio": 0.50, "Alto": 0.85}
        return base_map.get(cluster_label, 0.50)

    # Normalizo distancia: 0 = muy cercano al centroide de alto riesgo
    norm_dist = min(dist_to_high_risk / max_dist, 1.0)

    if cluster_label == "Alto":
        return round(1.0 - 0.33 * norm_dist, 4)
    elif cluster_label == "Medio":
        return round(0.66 - 0.32 * norm_dist, 4)
    else:
        return round(0.33 - 0.33 * norm_dist, 4)


def _nivel_from_score(score: float, levels: dict) -> str:
    if score <= levels["bajo"]["max"]:
        return "Bajo"
    elif score <= levels["medio"]["max"]:
        return "Medio"
    return "Alto"


def run_clustering(df_features: pd.DataFrame) -> pd.DataFrame:
    log.info("Iniciando KMeans clustering — %d clientes", len(df_features))

    X, feature_cols = _get_feature_matrix(df_features)

    k = PARAMS["clustering"]["n_clusters"]
    seed = PARAMS["clustering"]["random_state"]
    max_iter = PARAMS["clustering"]["max_iter"]

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    kmeans = KMeans(n_clusters=k, random_state=seed, max_iter=max_iter, n_init=10)
    labels = kmeans.fit_predict(X_scaled)

    centroids_scaled = kmeans.cluster_centers_
    # Centroids en espacio normalizado original (0-1)
    centroids_orig = scaler.inverse_transform(centroids_scaled).clip(0, 1)

    cluster_risk_map = _map_clusters_to_risk(centroids_orig)

    # Distancias al centroide de alto riesgo
    high_risk_cluster = next(c for c, r in cluster_risk_map.items() if r == "Alto")
    high_centroid_scaled = centroids_scaled[high_risk_cluster]
    dists_to_high = np.linalg.norm(X_scaled - high_centroid_scaled, axis=1)
    max_dist = dists_to_high.max()

    levels = PARAMS["risk_levels"]
    version = PARAMS["model"]["version"]
    run_date = str(date.today())

    result_rows = []
    for i, (idx, row) in enumerate(df_features.iterrows()):
        cluster_id = int(labels[i])
        cluster_label = cluster_risk_map[cluster_id]
        dist = float(dists_to_high[i])
        score = _score_from_cluster(cluster_label, dist, max_dist)
        nivel = _nivel_from_score(score, levels)

        top_features = sorted(
            zip(feature_cols, X.iloc[i].values),
            key=lambda x: x[1],
            reverse=True,
        )[:3]
        drivers = ", ".join(f"{f.replace('_norm','')}" for f, _ in top_features)

        result_rows.append({
            "customer_id": row.get(PARAMS["customer_id_col"], idx),
            "periodo": f"180d al {run_date}",
            "cluster": cluster_id,
            "cluster_label": cluster_label,
            "score_cliente": score,
            "nivel_riesgo_cliente": nivel,
            "principales_features": drivers,
            "dist_centroide_alto": round(dist, 4),
            "fecha_modelo": run_date,
            "version_modelo": version,
        })

    df_results = pd.DataFrame(result_rows)

    # Guardar centroides como JSON para trazabilidad
    centroids_data = {
        "version": version,
        "run_date": run_date,
        "feature_columns": feature_cols,
        "cluster_risk_map": {str(k): v for k, v in cluster_risk_map.items()},
        "centroids_normalized": centroids_orig.tolist(),
        "inertia": round(float(kmeans.inertia_), 4),
    }
    centroids_file = ROOT / "outputs" / "model_centroids.json"
    centroids_file.parent.mkdir(parents=True, exist_ok=True)
    centroids_file.write_text(json.dumps(centroids_data, ensure_ascii=False, indent=2))
    log.info("Centroides guardados en %s", centroids_file)

    dist_summary = df_results["nivel_riesgo_cliente"].value_counts().to_dict()
    log.info("Distribución de niveles de riesgo clientes: %s", dist_summary)

    return df_results
