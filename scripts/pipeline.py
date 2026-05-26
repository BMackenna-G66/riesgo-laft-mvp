#!/usr/bin/env python3
"""
Pipeline orquestador — Segmentación de Riesgo LA/FT/FPADM
Ejecuta el flujo end-to-end en orden:
  1. Extracción desde Redshift
  2. Feature engineering
  3. Modelo clientes (KMeans)
  4. Score jurisdicciones
  5. Score productos
  6. Score canales
  7. Score final consolidado
  8. Validaciones
  9. Exportación Excel + resumen ejecutivo

Uso:
    python pipeline.py
"""

import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FILE = ROOT / "logs" / f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("pipeline")

# Importaciones propias (en scripts/)
sys.path.insert(0, str(Path(__file__).parent))
from extract import extract_consolidado
from features import build_features
from model_clients import run_clustering
from score_jurisdictions import build_jurisdiction_scores
from score_products import assign_product_score_to_clients, build_products_df
from score_channels import assign_channel_score_to_clients, build_channels_df
from score_final import build_final_score
from validate import validate_pipeline
from export import export_excel, export_summary, export_frontend_json


def run():
    t0 = time.time()
    log.info("=" * 60)
    log.info("INICIO PIPELINE — SEGMENTACIÓN LA/FT/FPADM")
    log.info("=" * 60)

    # ── 1. Extracción ───────────────────────────────────────────
    log.info("PASO 1/9: Extracción desde Redshift…")
    df_raw = extract_consolidado()
    log.info("Clientes extraídos: %d", len(df_raw))

    if df_raw.empty:
        log.error("DataFrame vacío — abortando pipeline.")
        sys.exit(1)

    # ── 2. Feature engineering ──────────────────────────────────
    log.info("PASO 2/9: Feature engineering…")
    df_features = build_features(df_raw)

    # ── 3. Modelo clientes (KMeans) ─────────────────────────────
    log.info("PASO 3/9: Clustering KMeans clientes…")
    df_clients_results = run_clustering(df_features)

    # ── 4. Score jurisdicciones ─────────────────────────────────
    log.info("PASO 4/9: Score jurisdicciones…")
    df_jurisdiction = build_jurisdiction_scores(df_raw, df_raw)

    # ── 5. Score productos ──────────────────────────────────────
    log.info("PASO 5/9: Score productos…")
    df_products_clients = assign_product_score_to_clients(df_raw)
    df_products_detail = build_products_df()

    # ── 6. Score canales ────────────────────────────────────────
    log.info("PASO 6/9: Score canales…")
    df_channels_clients = assign_channel_score_to_clients(df_raw)
    df_channels_detail = build_channels_df()

    # ── 7. Score final consolidado ──────────────────────────────
    log.info("PASO 7/9: Score final consolidado…")
    df_final = build_final_score(
        df_clients_results,
        df_jurisdiction,
        df_products_clients,
        df_channels_clients,
    )

    # ── 8. Validaciones ─────────────────────────────────────────
    log.info("PASO 8/9: Validaciones…")
    is_valid, issues = validate_pipeline(df_raw, df_features, df_clients_results, df_final)
    if not is_valid:
        log.error("Pipeline completado con errores críticos — revisar logs.")
    else:
        log.info("Validaciones OK.")

    # ── 9. Exportación ──────────────────────────────────────────
    log.info("PASO 9/9: Exportando resultados…")
    excel_path = export_excel(
        df_features,
        df_clients_results,
        df_final,
        df_products_detail,
        df_channels_detail,
    )
    summary_path = export_summary(df_final, issues)
    export_frontend_json(df_final, df_raw)

    elapsed = round(time.time() - t0, 1)
    log.info("=" * 60)
    log.info("PIPELINE COMPLETADO en %.1fs", elapsed)
    log.info("Excel:    %s", excel_path)
    log.info("Resumen:  %s", summary_path)
    log.info("Log:      %s", LOG_FILE)
    log.info("=" * 60)

    return df_final


if __name__ == "__main__":
    run()
