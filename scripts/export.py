#!/usr/bin/env python3
"""
Exportación de resultados:
1. Excel con 4 pestañas: features, resultados clientes, resumen segmentos, score final
2. Resumen ejecutivo en texto plano (.txt)
3. docs/data/results.json para el dashboard GitHub Pages
"""

import json
import logging
from datetime import date
from pathlib import Path
from typing import List

import pandas as pd
import yaml

log = logging.getLogger("export")

ROOT = Path(__file__).parent.parent
OUTPUTS_DIR = ROOT / "outputs"
DOCS_DATA_DIR = ROOT / "docs" / "data"
PARAMS = yaml.safe_load((ROOT / "config" / "parameters.yaml").read_text())


def _get_output_path(suffix: str) -> Path:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    return OUTPUTS_DIR / f"segmentacion_laft_{date.today().isoformat()}_{suffix}"


def export_excel(
    df_features: pd.DataFrame,
    df_clients_results: pd.DataFrame,
    df_final: pd.DataFrame,
    df_products: pd.DataFrame,
    df_channels: pd.DataFrame,
) -> Path:
    path = _get_output_path("resultados.xlsx")
    log.info("Exportando Excel → %s", path)

    df_segment_summary = (
        df_final.groupby("nivel_riesgo_final")
        .agg(
            total_clientes=("customer_id", "count"),
            score_promedio=("score_final", "mean"),
            score_min=("score_final", "min"),
            score_max=("score_final", "max"),
        )
        .round(4)
        .reset_index()
    )

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        # Tab 1: Variables calculadas por cliente
        _write_sheet(writer, df_features, "01_variables_clientes", max_rows=100000)

        # Tab 2: Resultados modelo clientes
        _write_sheet(writer, df_clients_results, "02_resultados_clientes")

        # Tab 3: Score final consolidado
        df_final_sorted = df_final.sort_values("score_final", ascending=False)
        _write_sheet(writer, df_final_sorted, "03_score_final")

        # Tab 4: Resumen por segmento
        _write_sheet(writer, df_segment_summary, "04_resumen_segmentos")

        # Tab 5: Productos y canales parametrizados
        _write_sheet(writer, df_products, "05_productos")
        _write_sheet(writer, df_channels, "06_canales")

    log.info("Excel exportado: %s", path)
    return path


def _write_sheet(writer: pd.ExcelWriter, df: pd.DataFrame, sheet_name: str, max_rows: int = 1048576) -> None:
    df.head(max_rows).to_excel(writer, sheet_name=sheet_name, index=False)
    ws = writer.sheets[sheet_name]
    # Auto-ajuste de columnas
    for col in ws.columns:
        max_len = max(
            (len(str(cell.value)) if cell.value else 0 for cell in col),
            default=10,
        )
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 50)


def export_summary(df_final: pd.DataFrame, validation_issues: List[str]) -> Path:
    path = _get_output_path("resumen_ejecutivo.txt")
    run_date = date.today().isoformat()

    total = len(df_final)
    dist = df_final["nivel_riesgo_final"].value_counts().to_dict()
    bajo = dist.get("Bajo", 0)
    medio = dist.get("Medio", 0)
    alto = dist.get("Alto", 0)

    top20 = df_final.sort_values("score_final", ascending=False).head(20)[
        ["customer_id", "score_final", "nivel_riesgo_final", "principales_drivers"]
    ]

    # Top países por score_pais_origen (si disponible en df_final)
    driver_counts = df_final["principales_drivers"].str.split(", ").explode().value_counts().head(5)

    lines = [
        "=" * 70,
        "  RESUMEN EJECUTIVO — SEGMENTACIÓN DE RIESGO LA/FT/FPADM",
        "=" * 70,
        f"  Fecha de corrida:        {run_date}",
        f"  Versión del modelo:      {df_final['version_modelo'].iloc[0]}",
        "",
        "UNIVERSO EVALUADO",
        f"  Total clientes:          {total:,}",
        f"  Riesgo Bajo:             {bajo:,}  ({bajo/total:.1%})" if total > 0 else "",
        f"  Riesgo Medio:            {medio:,}  ({medio/total:.1%})" if total > 0 else "",
        f"  Riesgo Alto:             {alto:,}  ({alto/total:.1%})" if total > 0 else "",
        "",
        "TOP 20 CLIENTES MAYOR SCORE",
    ]

    for _, r in top20.iterrows():
        lines.append(
            f"  {str(r['customer_id']):<20} score={r['score_final']:.4f}  "
            f"nivel={r['nivel_riesgo_final']:<6}  drivers={r['principales_drivers']}"
        )

    lines += [
        "",
        "PRINCIPALES DRIVERS DE RIESGO (frecuencia en top clientes)",
    ]
    for driver, cnt in driver_counts.items():
        lines.append(f"  {driver:<20} {cnt} clientes")

    lines += [
        "",
        "SCORES POR FACTOR (promedio portfolio)",
        f"  Score cliente:           {df_final['score_cliente'].mean():.4f}",
        f"  Score jurisdiccion:      {df_final['score_jurisdiccion'].mean():.4f}",
        f"  Score producto:          {df_final['score_producto'].mean():.4f}",
        f"  Score canal:             {df_final['score_canal'].mean():.4f}",
        f"  Score final:             {df_final['score_final'].mean():.4f}",
    ]

    if validation_issues:
        lines += ["", "ALERTAS DE VALIDACIÓN"]
        for issue in validation_issues:
            lines.append(f"  ⚠  {issue}")

    lines += ["", "=" * 70]

    summary_text = "\n".join(lines)
    path.write_text(summary_text, encoding="utf-8")
    log.info("Resumen ejecutivo exportado: %s", path)
    print("\n" + summary_text + "\n")
    return path


def export_frontend_json(
    df_final: pd.DataFrame,
    df_clients_features: pd.DataFrame,
) -> Path:
    """Escribe docs/data/results.json para el dashboard GitHub Pages."""
    run_date = str(date.today())
    version = PARAMS["model"]["version"]
    weights = PARAMS["weights"]

    total = len(df_final)
    dist = df_final["nivel_riesgo_final"].value_counts().to_dict()

    segment_summary = []
    for nivel in ["Bajo", "Medio", "Alto"]:
        sub = df_final[df_final["nivel_riesgo_final"] == nivel]
        count = len(sub)
        segment_summary.append({
            "nivel": nivel,
            "total": count,
            "pct": round(count / total, 4) if total > 0 else 0,
            "score_avg": round(float(sub["score_final"].mean()), 4) if count > 0 else 0,
        })

    # Top 200 clientes por score desc (para la tabla del frontend)
    top = df_final.sort_values("score_final", ascending=False).head(200)
    top_clients = []
    for _, r in top.iterrows():
        # Buscar country_code desde df_clients_features si no está en df_final
        country = str(r.get("country_code", ""))
        if not country and "country_code" in df_clients_features.columns:
            mask = df_clients_features["customer_id"] == r["customer_id"]
            rows = df_clients_features.loc[mask, "country_code"]
            country = str(rows.values[0]) if len(rows) > 0 else ""
        top_clients.append({
            "customer_id": str(r["customer_id"]),
            "score_final": round(float(r["score_final"]), 4),
            "score_cliente": round(float(r["score_cliente"]), 4),
            "score_jurisdiccion": round(float(r["score_jurisdiccion"]), 4),
            "score_producto": round(float(r["score_producto"]), 4),
            "score_canal": round(float(r["score_canal"]), 4),
            "nivel_riesgo_final": str(r["nivel_riesgo_final"]),
            "nivel_riesgo_cliente": str(r.get("nivel_riesgo_cliente", "")),
            "principales_drivers": str(r.get("principales_drivers", "")),
            "country_code": country.upper() if country else "—",
        })

    # Riesgo por país de origen
    country_risk_summary = []
    if "country_code" in df_clients_features.columns:
        merged = df_final.merge(
            df_clients_features[["customer_id", "country_code"]].drop_duplicates("customer_id"),
            on="customer_id", how="left",
        )
        by_country = (
            merged.groupby("country_code")
            .agg(total_clients=("customer_id", "count"), avg_score=("score_final", "mean"))
            .reset_index()
            .sort_values("avg_score", ascending=False)
            .head(15)
        )
        country_risk_summary = [
            {
                "country_code": str(row["country_code"]),
                "country_name": str(row["country_code"]),
                "total_clients": int(row["total_clients"]),
                "avg_score": round(float(row["avg_score"]), 4),
            }
            for _, row in by_country.iterrows()
        ]

    payload = {
        "run_date": run_date,
        "model_version": version,
        "demo": False,
        "summary": {
            "total_clients": total,
            "bajo":  int(dist.get("Bajo",  0)),
            "medio": int(dist.get("Medio", 0)),
            "alto":  int(dist.get("Alto",  0)),
            "score_final_avg":        round(float(df_final["score_final"].mean()), 4),
            "score_cliente_avg":      round(float(df_final["score_cliente"].mean()), 4),
            "score_jurisdiccion_avg": round(float(df_final["score_jurisdiccion"].mean()), 4),
            "score_producto_avg":     round(float(df_final["score_producto"].mean()), 4),
            "score_canal_avg":        round(float(df_final["score_canal"].mean()), 4),
            "weights": weights,
        },
        "segment_summary": segment_summary,
        "top_clients": top_clients,
        "country_risk_summary": country_risk_summary,
    }

    DOCS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = DOCS_DATA_DIR / "results.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Frontend JSON actualizado: %s", out)
    return out
