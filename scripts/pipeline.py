#!/usr/bin/env python3
"""
Pipeline orquestador — Segmentación de Riesgo LA/FT/FPADM
Ejecuta el flujo end-to-end en orden:
  1. Ciclo de vida del cluster: enciende si está pausado, espera disponibilidad
  2. Extracción desde Redshift (db_prod via Data API)
  3. Apaga el cluster inmediatamente tras la extracción (ahorro de costos)
  4. Feature engineering
  5. Modelo clientes (KMeans)
  6. Score jurisdicciones
  7. Score productos
  8. Score canales
  9. Score final consolidado
  10. Validaciones
  11. Exportación Excel + resumen ejecutivo + dashboard JSON

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
LOG_FILE  = ROOT / "logs" / f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
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

sys.path.insert(0, str(Path(__file__).parent))

from extract            import extract_consolidado
from features           import build_features
from model_clients      import run_clustering
from score_jurisdictions import build_jurisdiction_scores
from score_products     import assign_product_score_to_clients, build_products_df
from score_channels     import assign_channel_score_to_clients, build_channels_df
from score_final        import build_final_score
from validate           import validate_pipeline
from export             import export_excel, export_summary, export_frontend_json
import cluster_control  as cc


# ── Ciclo de vida del cluster ──────────────────────────────────────────────

CLUSTER_POLL_S   = 15    # segundos entre polls de estado
CLUSTER_TIMEOUT  = 300   # máximo 5 minutos esperando que el cluster esté disponible


def _resume_and_wait() -> bool:
    """
    Asegura que el cluster esté disponible antes de extraer datos.
    Si está pausado, lo reanuda y espera hasta que esté listo.
    Retorna True si fue necesario reanudarlo (para pausarlo luego).
    """
    status = cc.get_status()
    raw    = status.get("status_raw", "unknown")

    if raw == "available":
        log.info("Cluster ya disponible (%s).", status.get("status_label", raw))
        return False

    if raw in ("paused",):
        log.info("Cluster pausado — iniciando reanudación…")
        cc.resume_cluster()
        we_resumed = True
    elif raw == "resuming":
        log.info("Cluster ya está reanudando — esperando disponibilidad…")
        we_resumed = True
    elif raw == "pausing":
        # Esperar a que termine de pausar y luego reanudar
        log.info("Cluster pausando — esperando que termine antes de reanudar…")
        deadline_pause = time.time() + CLUSTER_TIMEOUT
        while time.time() < deadline_pause:
            time.sleep(CLUSTER_POLL_S)
            status = cc.get_status()
            raw    = status.get("status_raw", "unknown")
            if raw == "paused":
                log.info("Cluster pausado — iniciando reanudación…")
                cc.resume_cluster()
                we_resumed = True
                break
            if raw == "available":
                log.info("Cluster disponible (canceló el pause).")
                return False
            log.info("  Cluster %s…", status.get("status_label", raw))
        else:
            raise TimeoutError("Cluster tardó demasiado en pausar.")
    else:
        raise RuntimeError(
            f"Cluster en estado inesperado '{raw}'. "
            "Verifica en AWS Console antes de continuar."
        )

    deadline = time.time() + CLUSTER_TIMEOUT
    while time.time() < deadline:
        time.sleep(CLUSTER_POLL_S)
        status = cc.get_status()
        raw    = status.get("status_raw", "unknown")
        remaining = int(deadline - time.time())
        log.info(
            "Esperando cluster… estado=%s (%ds restantes)",
            status.get("status_label", raw), remaining,
        )
        if raw == "available":
            log.info("✓ Cluster disponible.")
            return we_resumed

    raise TimeoutError(
        f"Cluster no disponible después de {CLUSTER_TIMEOUT}s. "
        "Verifica el estado en AWS Console."
    )


def _pause_cluster() -> None:
    """Pausa el cluster. Si ya está pausado, no hace nada."""
    try:
        status = cc.pause_cluster()
        cc.write_status_file(status)
        log.info(
            "Cluster pausado → %s.",
            status.get("status_label", status.get("status_raw", "?")),
        )
    except Exception as exc:
        log.warning("No se pudo pausar el cluster: %s", exc)


# ── Pipeline principal ─────────────────────────────────────────────────────

def run():
    t0 = time.time()
    log.info("=" * 60)
    log.info("INICIO PIPELINE — SEGMENTACIÓN LA/FT/FPADM")
    log.info("=" * 60)

    we_resumed = False

    # ── 0. Ciclo de vida — encender cluster ─────────────────────────────
    log.info("PASO 0/9: Verificando disponibilidad del cluster…")
    try:
        we_resumed = _resume_and_wait()
    except (RuntimeError, TimeoutError) as exc:
        log.error("No se puede continuar: %s", exc)
        sys.exit(1)

    # ── 1. Extracción — dentro de try/finally para pausar siempre ───────
    log.info("PASO 1/9: Extracción desde Redshift (db_prod)…")
    df_raw = None
    try:
        df_raw = extract_consolidado()
        log.info("Clientes extraídos: %d", len(df_raw))
    finally:
        # Pausar cluster inmediatamente tras la extracción (ahorra costos)
        log.info("Pausando cluster tras extracción…")
        _pause_cluster()

    if df_raw is None or df_raw.empty:
        log.error("DataFrame vacío — abortando pipeline.")
        sys.exit(1)

    # ── 2. Feature engineering ──────────────────────────────────────────
    log.info("PASO 2/9: Feature engineering…")
    df_features = build_features(df_raw)

    # ── 3. Modelo clientes (KMeans) ─────────────────────────────────────
    log.info("PASO 3/9: Clustering KMeans clientes…")
    df_clients_results = run_clustering(df_features)

    # ── 4. Score jurisdicciones ─────────────────────────────────────────
    log.info("PASO 4/9: Score jurisdicciones…")
    df_jurisdiction = build_jurisdiction_scores(df_raw)

    # ── 5. Score productos ──────────────────────────────────────────────
    log.info("PASO 5/9: Score productos…")
    df_products_clients = assign_product_score_to_clients(df_raw)
    df_products_detail  = build_products_df()

    # ── 6. Score canales ────────────────────────────────────────────────
    log.info("PASO 6/9: Score canales…")
    df_channels_clients = assign_channel_score_to_clients(df_raw)
    df_channels_detail  = build_channels_df()

    # ── 7. Score final consolidado ──────────────────────────────────────
    log.info("PASO 7/9: Score final consolidado…")
    df_final = build_final_score(
        df_clients_results,
        df_jurisdiction,
        df_products_clients,
        df_channels_clients,
    )

    # ── 8. Validaciones ─────────────────────────────────────────────────
    log.info("PASO 8/9: Validaciones…")
    is_valid, issues = validate_pipeline(df_raw, df_features, df_clients_results, df_final)
    if not is_valid:
        log.error("Pipeline completado con errores críticos — revisar logs.")
    else:
        log.info("Validaciones OK.")

    # ── 9. Exportación ──────────────────────────────────────────────────
    log.info("PASO 9/9: Exportando resultados…")
    excel_path   = export_excel(
        df_features, df_clients_results, df_final,
        df_products_detail, df_channels_detail,
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
