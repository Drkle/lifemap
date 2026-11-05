"""Endpoints de LifeMap (Entrega 1)."""

from __future__ import annotations

from datetime import date, datetime
from time import perf_counter
from typing import Any

from bson import ObjectId
from flask import Blueprint, current_app, jsonify, request

from . import config
from .consultas import (ORDENES_STATS, PROYECCION_NEGOCIO, filtro_near, filtro_stats,
                        filtro_within, pipeline_zona)
from .prediccion import ModeloNoDisponible
from .tasas import MIN_DIAS_NEGOCIO_DEFECTO
from .validacion import (booleano, categoria, entero, opcion, poligono, punto,
                         texto_resena)

bp = Blueprint("lifemap", __name__)


def serializar(valor: Any) -> Any:
    if isinstance(valor, ObjectId):
        return str(valor)
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    if isinstance(valor, float):
        return round(valor, 4)
    if isinstance(valor, dict):
        return {clave: serializar(item) for clave, item in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [serializar(item) for item in valor]
    return valor


def _db():
    return current_app.config["DB"]


def _negocios():
    return _db()[config.NEGOCIOS_COLLECTION]


def _respuesta(resultados: list[dict[str, Any]], parametros: dict[str, Any], inicio: float, **extra):
    return jsonify(
        total_devuelto=len(resultados),
        parametros=parametros,
        tiempo_ms=round((perf_counter() - inicio) * 1000, 3),
        **extra,
        resultados=serializar(resultados),
    )


@bp.get("/")
def indice():
    return jsonify(
        proyecto="LifeMap: reputación, ubicación y supervivencia de negocios",
        endpoints={
            "GET /health": "estado de cada servicio y commit desplegado",
            "GET /businesses/near": "lat, lon, radio (m), categoria?, limit?  ($near)",
            "POST /businesses/within": "cuerpo: Polygon GeoJSON; ?categoria, ?limit  ($geoWithin)",
            "GET /zones/summary": "lat, lon, radio (m), categoria?, agrupar=categoria?, min_dias?  ($geoNear)",
            "GET /stats/closure": "por=categoria|celda, min_dias?, orden?, desc?, limit?",
            "POST /predict": '{"texto": "..."}  sentimiento de un texto nuevo',
        },
        version=config.APP_VERSION,
        commit=config.APP_COMMIT,
    )


@bp.get("/businesses/near")
def businesses_near():
    inicio = perf_counter()
    lat, lon, radio, limit = punto(request.args)
    cat = categoria(request.args.get("categoria"))
    resultados = list(_negocios().find(filtro_near(lat, lon, radio, cat), PROYECCION_NEGOCIO).limit(limit))
    return _respuesta(resultados, {"lat": lat, "lon": lon, "radio": radio, "categoria": cat, "limit": limit}, inicio)


@bp.post("/businesses/within")
def businesses_within():
    inicio = perf_counter()
    geometria = poligono(request.get_json(silent=True))
    cat = categoria(request.args.get("categoria"))
    limit = entero(request.args.get("limit", 100), "limit", minimo=1, maximo=5000)
    resultados = list(_negocios().find(filtro_within(geometria, cat), PROYECCION_NEGOCIO).limit(limit))
    return _respuesta(resultados, {"categoria": cat, "limit": limit, "poligono": geometria}, inicio)


@bp.get("/zones/summary")
def zones_summary():
    inicio = perf_counter()
    lat, lon, radio, _ = punto(request.args)
    cat = categoria(request.args.get("categoria"))
    agrupar = opcion(request.args.get("agrupar"), "agrupar", {"ninguno", "categoria"}, "ninguno")
    min_dias = entero(request.args.get("min_dias", MIN_DIAS_NEGOCIO_DEFECTO), "min_dias", minimo=0, maximo=10**9)
    resultados = list(_negocios().aggregate(pipeline_zona(lat, lon, radio, cat, agrupar)))
    for fila in resultados:
        fila["cumple_minimo"] = fila.get("dias_negocio", 0) >= min_dias
    return _respuesta(
        resultados,
        {"lat": lat, "lon": lon, "radio": radio, "categoria": cat, "agrupar": agrupar, "min_dias": min_dias},
        inicio,
        nota="tasa_cierre = cierres / (días-negocio / 365) * 100; si cumple_minimo es false, el grupo es "
             "demasiado pequeño para comparar su tasa.",
    )


@bp.get("/stats/closure")
def stats_closure():
    inicio = perf_counter()
    por = opcion(request.args.get("por"), "por", {"categoria", "celda"}, "categoria")
    min_dias = entero(request.args.get("min_dias", MIN_DIAS_NEGOCIO_DEFECTO), "min_dias", minimo=0, maximo=10**9)
    limit = entero(request.args.get("limit", 50), "limit", minimo=1, maximo=5000)
    orden = opcion(request.args.get("orden"), "orden", ORDENES_STATS, "tasa_cierre")
    desc = booleano(request.args.get("desc", "true"), "desc")
    coleccion = f"{config.TASAS_PREFIX}tasas_{por}"
    resultados = list(
        _db()[coleccion].find(filtro_stats(min_dias)).sort(orden, -1 if desc else 1).limit(limit)
    )
    meta = _db()[f"{config.TASAS_PREFIX}tasas_meta"].find_one({"_id": "tasas"}) or {}
    return _respuesta(
        resultados,
        {"por": por, "min_dias": min_dias, "orden": orden, "desc": desc, "limit": limit},
        inicio,
        coleccion=coleccion,
        resumen={k: meta.get(k) for k in ("negocios", "cierres", "dias_negocio", "tasa_global", "calculado_en")},
    )


@bp.route("/predict", methods=["GET", "POST"])
def predict():
    inicio = perf_counter()
    texto = texto_resena(request.get_json(silent=True), request.args)
    predictor = current_app.config["PREDICTOR"]
    try:
        resultado = predictor.predecir(texto)
    except ModeloNoDisponible as exc:
        return jsonify(error=str(exc)), 503
    return jsonify(texto=texto, tiempo_ms=round((perf_counter() - inicio) * 1000, 3), **resultado)
