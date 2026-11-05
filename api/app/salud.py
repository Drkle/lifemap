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
