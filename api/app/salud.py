"""Sondas de estado de los servicios para /health."""

from __future__ import annotations

import json
from typing import Any, Callable
from urllib.request import urlopen

from . import config

TIEMPO_MAXIMO_S = 2.5


def _get_json(url: str) -> Any:
    with urlopen(url, timeout=TIEMPO_MAXIMO_S) as respuesta:  # noqa: S310 - URL interna configurada
        return json.loads(respuesta.read().decode("utf-8"))


def sonda_spark() -> dict[str, Any]:
    """Estado del master de Spark y workers vivos (UI JSON del master standalone)."""
    try:
        datos = _get_json(f"{config.SPARK_UI_URL}/json/")
        vivos = int(datos.get("aliveworkers", 0))
        estado = "ok" if datos.get("status") == "ALIVE" and vivos >= 1 else "error"
        return {"estado": estado, "workers": vivos}
    except Exception as exc:  # noqa: BLE001
        return {"estado": "error", "detalle": type(exc).__name__}


def sonda_dask() -> dict[str, Any]:
    """Estado del scheduler de Dask y número de workers."""
    try:
        conteos = _get_json(f"{config.DASK_DASHBOARD_URL}/json/counts.json")
        workers = int(conteos.get("servers", conteos.get("workers", 0)))
        return {"estado": "ok" if workers >= 2 else "error", "workers": workers}
    except Exception as exc:  # noqa: BLE001
        return {"estado": "error", "detalle": type(exc).__name__}


SONDAS_POR_DEFECTO: dict[str, Callable[[], dict[str, Any]]] = {
    "spark": sonda_spark,
    "dask": sonda_dask,
}


def sonda_kafka(db):
    from kafka import KafkaConsumer, TopicPartition
    consumidor = None
    try:
        consumidor = KafkaConsumer(bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS, group_id=None,
            request_timeout_ms=4000, api_version_auto_timeout_ms=2500)
        particiones = consumidor.partitions_for_topic("reviews")
        if not particiones:
            return {"estado": "error", "detalle": "Topic reviews no disponible"}
        finales = consumidor.end_offsets([TopicPartition("reviews", p) for p in particiones])
        meta = db.streaming_meta.find_one({"_id": "progreso"}) or {}
        procesados = meta.get("offsets", {})
        lag = sum(max(0, fin - int(procesados.get(str(tp.partition), 0))) for tp, fin in finales.items())
        from datetime import datetime, timezone
        actualizado = meta.get("actualizado_en")
        edad = (datetime.now(timezone.utc).replace(tzinfo=None) - actualizado.replace(tzinfo=None)).total_seconds() if actualizado else None
        progreso = meta.get("progreso_en")
        edad_progreso = (datetime.now(timezone.utc).replace(tzinfo=None) - progreso.replace(tzinfo=None)).total_seconds() if progreso else None
        listo = meta.get("activo", False) and "offsets" in meta and edad is not None and 0 <= edad < 60
        return {"estado": "ok" if listo else "error", "particiones": len(particiones),
                "retraso_mensajes": lag, "segundos_desde_latido": edad,
                "segundos_desde_progreso": edad_progreso, "consumidor_activo": meta.get("activo", False)}
    except Exception as exc:
        return {"estado": "error", "detalle": type(exc).__name__}
    finally:
        if consumidor:
            consumidor.close()
