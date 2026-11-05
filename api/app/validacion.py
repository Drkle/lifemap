"""Validación reutilizable de parámetros de la API LifeMap."""

from __future__ import annotations

import re
from typing import Any, Mapping


class ErrorValidacion(ValueError):
    """Error de entrada que debe convertirse en una respuesta HTTP 400."""


def _numero(valor: Any, nombre: str) -> float:
    if valor is None or isinstance(valor, bool):
        raise ErrorValidacion(f"Falta el parámetro numérico '{nombre}'.")
    try:
        numero = float(valor)
    except (TypeError, ValueError) as exc:
        raise ErrorValidacion(f"'{nombre}' debe ser numérico.") from exc
    if numero != numero or numero in (float("inf"), float("-inf")):
        raise ErrorValidacion(f"'{nombre}' debe ser un número finito.")
    return numero


def entero(valor: Any, nombre: str, *, minimo: int, maximo: int) -> int:
    if valor is None:
        raise ErrorValidacion(f"Falta el parámetro entero '{nombre}'.")
    if isinstance(valor, bool) or not re.fullmatch(r"[+-]?\d+", str(valor).strip()):
        raise ErrorValidacion(f"'{nombre}' debe ser un número entero.")
    numero = int(valor)
    if not minimo <= numero <= maximo:
        raise ErrorValidacion(f"'{nombre}' debe estar entre {minimo} y {maximo}.")
    return numero


def punto(parametros: Mapping[str, Any]) -> tuple[float, float, float, int]:
    """Valida latitud, longitud, radio en metros y límite."""

    lat = _numero(parametros.get("lat"), "lat")
    lon = _numero(parametros.get("lon"), "lon")
    radio = _numero(parametros.get("radio"), "radio")
    limit = entero(parametros.get("limit", 100), "limit", minimo=1, maximo=1000)
    if not -90 <= lat <= 90:
        raise ErrorValidacion("'lat' debe estar entre -90 y 90.")
    if not -180 <= lon <= 180:
        raise ErrorValidacion("'lon' debe estar entre -180 y 180.")
    if not 0 < radio <= 50_000:
        raise ErrorValidacion("'radio' debe ser mayor que 0 y menor o igual a 50000 metros.")
    return lat, lon, radio, limit


def poligono(cuerpo: Any) -> dict[str, Any]:
    """Valida un Polygon GeoJSON y devuelve su geometría."""

    if not isinstance(cuerpo, dict):
        raise ErrorValidacion("El cuerpo debe ser un objeto JSON.")
    geometria = cuerpo.get("geometry", cuerpo)
    if not isinstance(geometria, dict) or geometria.get("type") != "Polygon":
        raise ErrorValidacion("La geometría debe tener type='Polygon'.")
    anillos = geometria.get("coordinates")
    if not isinstance(anillos, list) or not anillos:
        raise ErrorValidacion("El polígono debe contener al menos un anillo.")
    for indice, anillo in enumerate(anillos):
        if not isinstance(anillo, list) or len(anillo) < 4:
            raise ErrorValidacion(f"El anillo {indice} debe tener al menos 4 posiciones.")
        if anillo[0] != anillo[-1]:
            raise ErrorValidacion(f"El anillo {indice} debe estar cerrado.")
        for posicion in anillo:
            if not isinstance(posicion, list) or len(posicion) != 2:
                raise ErrorValidacion("Cada posición debe ser [longitud, latitud].")
            lon = _numero(posicion[0], "longitud")
            lat = _numero(posicion[1], "latitud")
            if not -180 <= lon <= 180 or not -90 <= lat <= 90:
                raise ErrorValidacion("Una posición del polígono está fuera de rango.")
    return {"type": "Polygon", "coordinates": anillos}


def booleano(valor: Any, nombre: str) -> bool:
    texto = str(valor).lower()
    if texto in {"1", "true", "si", "sí"}:
        return True
    if texto in {"0", "false", "no"}:
        return False
    raise ErrorValidacion(f"'{nombre}' debe ser true o false.")


def campo_orden(valor: Any) -> str:
    campo = str(valor or "n")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", campo):
        raise ErrorValidacion("'orden' contiene caracteres no permitidos.")
    return campo


def categoria(valor: Any) -> str | None:
    """Categoría principal opcional (texto corto: letras, números, espacios y & ' - / ( ) ,)."""

    if valor is None or str(valor).strip() == "":
        return None
    texto = str(valor).strip()
    if len(texto) > 80 or not re.fullmatch(r"[\w &'\-/(),.]+", texto):
        raise ErrorValidacion("'categoria' contiene caracteres no permitidos o es muy larga.")
    return texto


def opcion(valor: Any, nombre: str, permitidas: set[str], defecto: str) -> str:
    texto = str(valor if valor is not None else defecto).strip().lower()
    if texto not in permitidas:
        raise ErrorValidacion(f"'{nombre}' debe ser uno de: {', '.join(sorted(permitidas))}.")
    return texto


def texto_resena(cuerpo: Any, args: Mapping[str, Any]) -> str:
    """Texto para /predict: JSON {"texto": "..."} (o "text"), o ?texto= en la URL."""

    texto = None
    if isinstance(cuerpo, dict):
        texto = cuerpo.get("texto", cuerpo.get("text"))
    if texto is None:
        texto = args.get("texto")
    if not isinstance(texto, str) or not texto.strip():
        raise ErrorValidacion("Falta 'texto' (cadena no vacía).")
    if len(texto) > 5000:
        raise ErrorValidacion("'texto' no puede superar 5000 caracteres.")
    return texto.strip()
