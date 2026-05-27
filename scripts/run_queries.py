#!/usr/bin/env python3
"""
Orquestador de queries SQL — ejecuta todas las queries en queries/ contra Redshift.

Ciclo de vida del cluster:
  1. Enciende el cluster si está pausado y espera hasta disponibilidad (máx 5 min)
  2. Ejecuta cada archivo *.sql en queries/ en orden alfabético
  3. Guarda resultados en outputs/{nombre_query}.csv
  4. SIEMPRE pausa el cluster al terminar (incluso si hay errores)

Uso:
    cd scripts
    python run_queries.py

    # Solo un query específico:
    python run_queries.py 05_consolidado.sql

    # Con límite de filas (para pruebas):
    MAX_ROWS=5000 python run_queries.py
"""

import logging
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("run_queries")

sys.path.insert(0, str(Path(__file__).parent))

from db              import load_sql, query_to_df
import cluster_control as cc

OUTPUTS_DIR    = ROOT / "outputs"
QUERIES_DIR    = ROOT / "queries"
POLL_S         = 15     # segundos entre polls de estado del cluster
TIMEOUT_S      = 300    # máximo 5 minutos esperando disponibilidad
MAX_ROWS       = int(os.getenv("MAX_ROWS", 0)) or None   # 0 = sin límite


# ── Ciclo de vida del cluster ──────────────────────────────────────────────

def _resume_and_wait() -> bool:
    """
    Asegura que el cluster esté disponible.
    Si está pausado, lo reanuda y espera hasta que esté listo.
    Retorna True si fue necesario reanudarlo.
    """
    status = cc.get_status()
    raw    = status.get("status_raw", "unknown")

    if raw == "available":
        log.info("✓ Cluster ya disponible.")
        return False

    if raw == "paused":
        log.info("Cluster pausado — reanudando…")
        cc.resume_cluster()
    elif raw == "resuming":
        log.info("Cluster ya está reanudando — esperando…")
    elif raw == "pausing":
        # Esperar a que termine de pausar, luego reanudar
        log.info("Cluster pausando — esperando que complete para reanudar…")
        deadline_p = time.time() + TIMEOUT_S
        while time.time() < deadline_p:
            time.sleep(POLL_S)
            status = cc.get_status()
            raw    = status.get("status_raw", "unknown")
            if raw == "paused":
                log.info("Cluster pausado — reanudando…")
                cc.resume_cluster()
                break
            if raw == "available":
                log.info("✓ Cluster disponible (canceló pause).")
                return False
            log.info("  Cluster %s…", status.get("status_label", raw))
        else:
            raise TimeoutError("Cluster tardó demasiado en pausar.")
    else:
        raise RuntimeError(
            f"Cluster en estado inesperado: '{raw}'. "
            "Verifica en AWS Console."
        )

    deadline = time.time() + TIMEOUT_S
    while time.time() < deadline:
        time.sleep(POLL_S)
        status = cc.get_status()
        raw    = status.get("status_raw", "unknown")
        log.info(
            "  Cluster %s… (%ds restantes)",
            status.get("status_label", raw),
            int(deadline - time.time()),
        )
        if raw == "available":
            log.info("✓ Cluster disponible.")
            return True

    raise TimeoutError(f"Cluster no disponible después de {TIMEOUT_S}s.")


def _pause_cluster() -> None:
    """Pausa el cluster. Silencioso si ya está pausado o hay error."""
    try:
        status = cc.pause_cluster()
        cc.write_status_file(status)
        log.info("⏸  Cluster pausado → %s", status.get("status_label", "?"))
    except Exception as exc:
        log.warning("No se pudo pausar el cluster: %s", exc)


# ── Ejecución de queries ───────────────────────────────────────────────────

def _get_query_files() -> list:
    """
    Retorna lista de archivos .sql en queries/ en orden alfabético.
    Si se pasa un nombre de archivo como argumento, solo devuelve ese.
    """
    if len(sys.argv) > 1:
        target = sys.argv[1]
        f = QUERIES_DIR / target
        if not f.exists():
            log.error("Query no encontrada: %s", f)
            sys.exit(1)
        return [f]
    return sorted(QUERIES_DIR.glob("*.sql"))


def _run_query(sql_file: Path) -> None:
    """Ejecuta una query y guarda el resultado como CSV."""
    name = sql_file.stem
    log.info("─── %s ───", name)

    sql = load_sql(sql_file.name)

    # Inyectar LIMIT si MAX_ROWS está configurado (solo para pruebas)
    if MAX_ROWS and "LIMIT" not in sql.upper().split("--")[0]:
        sql = sql.rstrip().rstrip(";") + f"\nLIMIT {MAX_ROWS}"
        log.info("  [TEST] Limitado a %d filas", MAX_ROWS)

    t = time.time()
    df = query_to_df(sql)
    elapsed = round(time.time() - t, 1)

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUTS_DIR / f"{name}.csv"
    df.to_csv(out_path, index=False)

    log.info(
        "  ✓ %d filas × %d cols → %s  (%.1fs)",
        len(df), len(df.columns), out_path.name, elapsed,
    )


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    t0 = time.time()
    log.info("=" * 60)
    log.info("RUN QUERIES — SEGMENTACIÓN LA/FT/FPADM")
    log.info("=" * 60)

    query_files = _get_query_files()
    if not query_files:
        log.error("No se encontraron archivos .sql en %s", QUERIES_DIR)
        sys.exit(1)

    log.info("Queries a ejecutar: %d", len(query_files))
    for f in query_files:
        log.info("  • %s", f.name)

    # ── 1. Encender cluster ──────────────────────────────────────────────
    log.info("")
    log.info("PASO 1/3: Encendiendo cluster…")
    try:
        _resume_and_wait()
    except (RuntimeError, TimeoutError) as exc:
        log.error("No se puede continuar: %s", exc)
        sys.exit(1)

    # ── 2. Ejecutar queries — pausar cluster siempre en finally ─────────
    errors = []
    try:
        log.info("")
        log.info("PASO 2/3: Ejecutando queries…")
        for sql_file in query_files:
            try:
                _run_query(sql_file)
            except Exception as exc:
                log.error("Error en '%s': %s", sql_file.name, exc)
                errors.append((sql_file.name, str(exc)))
    finally:
        # ── 3. Siempre pausar cluster al terminar ────────────────────────
        log.info("")
        log.info("PASO 3/3: Pausando cluster…")
        _pause_cluster()

    elapsed = round(time.time() - t0, 1)
    log.info("")
    log.info("=" * 60)
    if errors:
        log.warning("COMPLETADO CON %d ERROR(ES) en %.1fs", len(errors), elapsed)
        for name, err in errors:
            log.warning("  ✗ %s: %s", name, err)
    else:
        log.info("COMPLETADO EXITOSAMENTE en %.1fs", elapsed)
        log.info("CSVs en: %s", OUTPUTS_DIR)
    log.info("=" * 60)

    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
