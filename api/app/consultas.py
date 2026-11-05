"""Constructores puros de filtros y pipelines de MongoDB (se prueban sin base de datos)."""

from __future__ import annotations

from typing import Any

from .tasas import DIAS_POR_ANIO

# Campos que devuelven los endpoints de negocios (no se envían listas largas ni metadatos).
PROYECCION_NEGOCIO = {
    "nombre": 1, "ciudad": 1, "location": 1, "geohash": 1, "estrellas": 1,
    "categoria_principal": 1, "is_open": 1, "primera_resena": 1, "ultima_resena": 1,
    "n_resenas": 1, "dias_negocio": 1, "evento": 1, "censurado": 1,
    "pct_negativas": 1, "sentimiento_medio": 1,
}


def _punto(lat: float, lon: float) -> dict[str, Any]:
    return {"type": "Point", "coordinates": [lon, lat]}


def _con_categoria(filtro: dict[str, Any], categoria: str | None) -> dict[str, Any]:
    if categoria:
        filtro["categoria_principal"] = categoria
    return filtro


def filtro_near(lat: float, lon: float, radio: float, categoria: str | None = None) -> dict[str, Any]:
    """$near: negocios a menos de ``radio`` metros, ordenados por distancia."""
    return _con_categoria(
        {"location": {"$near": {"$geometry": _punto(lat, lon), "$maxDistance": radio}}}, categoria
    )


def filtro_within(geometria: dict[str, Any], categoria: str | None = None) -> dict[str, Any]:
    """$geoWithin: negocios dentro de un polígono GeoJSON."""
    return _con_categoria({"location": {"$geoWithin": {"$geometry": geometria}}}, categoria)


def _tasa_expr(cierres: str, dias: str) -> dict[str, Any]:
    """cierres / (días-negocio / 365) * 100, calculado dentro de MongoDB."""
    return {
        "$cond": [
            {"$gt": [dias, 0]},
            {"$multiply": [{"$divide": [cierres, {"$divide": [dias, DIAS_POR_ANIO]}]}, 100]},
            None,
        ]
    }


def pipeline_zona(
    lat: float, lon: float, radio: float, categoria: str | None = None, agrupar: str | None = None
) -> list[dict[str, Any]]:
    """$geoNear + $group: sentimiento medio y tasa de cierre alrededor de un punto."""
    geo_near: dict[str, Any] = {
        "near": _punto(lat, lon),
        "distanceField": "distancia_m",
        "maxDistance": radio,
        "spherical": True,
        "key": "location",
    }
    if categoria:
        geo_near["query"] = {"categoria_principal": categoria}
    return [
        {"$geoNear": geo_near},
        {
            "$group": {
                "_id": "$categoria_principal" if agrupar == "categoria" else None,
                "negocios": {"$sum": 1},
                "cierres": {"$sum": "$evento"},
                "dias_negocio": {"$sum": "$dias_negocio"},
                "resenas": {"$sum": "$n_resenas"},
                "negativas": {"$sum": "$negativas"},
                "sentimiento_medio": {"$avg": "$sentimiento_medio"},
                "pct_negativas_medio": {"$avg": "$pct_negativas"},
                "estrellas_media": {"$avg": "$estrellas"},
                "distancia_media_m": {"$avg": "$distancia_m"},
            }
        },
        {
            "$project": {
                "_id": 0,
                "grupo": "$_id",
                "negocios": 1,
                "cierres": 1,
                "abiertos": {"$subtract": ["$negocios", "$cierres"]},
                "dias_negocio": 1,
                "anios_negocio": {"$divide": ["$dias_negocio", DIAS_POR_ANIO]},
                "tasa_cierre": _tasa_expr("$cierres", "$dias_negocio"),
                "resenas": 1,
                "pct_negativas_resenas": {
                    "$cond": [{"$gt": ["$resenas", 0]},
                              {"$multiply": [{"$divide": ["$negativas", "$resenas"]}, 100]}, None]
                },
                "sentimiento_medio": 1,
                "pct_negativas_medio": 1,
                "estrellas_media": 1,
                "distancia_media_m": 1,
            }
        },
        {"$sort": {"negocios": -1}},
    ]


ORDENES_STATS = {"tasa_cierre", "cierres", "dias_negocio", "negocios", "anios_negocio", "pct_negativas"}


def filtro_stats(min_dias: int) -> dict[str, Any]:
    """Solo grupos con al menos ``min_dias`` días-negocio (no se concluye de grupos pequeños)."""
    return {"dias_negocio": {"$gte": min_dias}}
