#!/usr/bin/env python3
"""
Control del cluster Redshift via boto3.
Uso:  python cluster_control.py [status|resume|pause]

Las credenciales AWS se leen desde variables de entorno (.env o GitHub Secrets).
"""

import json
import logging
import os
import sys
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("cluster_control")

CLUSTER_ID = os.getenv("REDSHIFT_CLUSTER_ID", "compliance-redshift-cluster")
AWS_REGION  = os.getenv("AWS_REGION", "us-east-1")

STATUS_FILE = Path(__file__).parent.parent / "docs" / "data" / "cluster_status.json"

# Mapeo de estados AWS → etiqueta legible
STATUS_LABELS = {
    "available":         "Disponible",
    "paused":            "Pausado",
    "resuming":          "Reanudando",
    "pausing":           "Pausando",
    "creating":          "Creando",
    "deleting":          "Eliminando",
    "rebooting":         "Reiniciando",
    "modifying":         "Modificando",
    "maintenance":       "Mantenimiento",
    "snapshotting":      "Snapshot",
    "hardware-failure":  "Error hardware",
    "incompatible-parameters": "Error parámetros",
}


def _client():
    return boto3.client(
        "redshift",
        region_name=AWS_REGION,
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    )


def get_status() -> dict:
    """Retorna dict con estado actual del cluster."""
    try:
        resp = _client().describe_clusters(ClusterIdentifier=CLUSTER_ID)
        cluster = resp["Clusters"][0]
        raw_status = cluster.get("ClusterStatus", "unknown").lower()
        return {
            "cluster_id":       CLUSTER_ID,
            "status_raw":       raw_status,
            "status_label":     STATUS_LABELS.get(raw_status, raw_status.capitalize()),
            "node_type":        cluster.get("NodeType", ""),
            "number_of_nodes":  cluster.get("NumberOfNodes", 0),
            "endpoint":         cluster.get("Endpoint", {}).get("Address", ""),
            "database_name":    cluster.get("DBName", ""),
            "availability_zone": cluster.get("AvailabilityZone", ""),
            "checked_at":       _now_iso(),
        }
    except ClientError as e:
        log.error("Error consultando estado del cluster: %s", e)
        return {
            "cluster_id":   CLUSTER_ID,
            "status_raw":   "error",
            "status_label": "Error al consultar",
            "error":        str(e),
            "checked_at":   _now_iso(),
        }


def resume_cluster() -> dict:
    """Reanuda el cluster si está pausado. Retorna estado resultante."""
    log.info("Reanudando cluster %s …", CLUSTER_ID)
    status = get_status()
    if status["status_raw"] == "available":
        log.info("El cluster ya está disponible — no se requiere acción.")
        return status
    if status["status_raw"] not in ("paused",):
        log.warning("Estado actual '%s' no permite reanudar directamente.", status["status_raw"])
        return status
    try:
        _client().resume_cluster(ClusterIdentifier=CLUSTER_ID)
        log.info("Solicitud de reanudación enviada. El cluster tardará ~2-3 minutos.")
        time.sleep(5)
        return get_status()
    except ClientError as e:
        log.error("Error al reanudar: %s", e)
        status["error"] = str(e)
        return status


def pause_cluster() -> dict:
    """Pausa el cluster si está disponible. Retorna estado resultante."""
    log.info("Pausando cluster %s …", CLUSTER_ID)
    status = get_status()
    if status["status_raw"] == "paused":
        log.info("El cluster ya está pausado — no se requiere acción.")
        return status
    if status["status_raw"] not in ("available",):
        log.warning("Estado actual '%s' no permite pausar directamente.", status["status_raw"])
        return status
    try:
        _client().pause_cluster(ClusterIdentifier=CLUSTER_ID)
        log.info("Solicitud de pausa enviada.")
        time.sleep(5)
        return get_status()
    except ClientError as e:
        log.error("Error al pausar: %s", e)
        status["error"] = str(e)
        return status


def write_status_file(status: dict) -> None:
    """Escribe docs/data/cluster_status.json para el dashboard."""
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(
        json.dumps(status, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log.info("cluster_status.json actualizado: %s", status.get("status_label"))


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("status", "resume", "pause"):
        print("Uso: python cluster_control.py [status|resume|pause]")
        sys.exit(1)

    action = sys.argv[1]

    if action == "status":
        status = get_status()
    elif action == "resume":
        status = resume_cluster()
    elif action == "pause":
        status = pause_cluster()

    write_status_file(status)
    log.info("Estado final: %s", status.get("status_label"))
    print(json.dumps(status, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
