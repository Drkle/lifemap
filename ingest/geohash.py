"""Codificación geohash sin dependencias externas.

Se usa el mismo archivo en ingest/ y en spark/jobs/ (cada imagen Docker tiene su propio
contexto de construcción). La precisión 6 da celdas de ~1,2 km x 0,6 km en latitudes medias.
"""

from __future__ import annotations

_BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"
_DECODE = {c: i for i, c in enumerate(_BASE32)}


def encode(lat: float, lon: float, precision: int = 6) -> str:
    """Devuelve el geohash de (lat, lon) con ``precision`` caracteres."""

    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError("Coordenadas fuera de rango")
    lat_rango = [-90.0, 90.0]
    lon_rango = [-180.0, 180.0]
    resultado = []
    bits = 0
    valor = 0
    par = True  # el primer bit corresponde a la longitud
    while len(resultado) < precision:
        rango, coord = (lon_rango, lon) if par else (lat_rango, lat)
        medio = (rango[0] + rango[1]) / 2
        if coord >= medio:
            valor = (valor << 1) | 1
            rango[0] = medio
        else:
            valor <<= 1
            rango[1] = medio
        par = not par
        bits += 1
        if bits == 5:
            resultado.append(_BASE32[valor])
            bits = 0
            valor = 0
    return "".join(resultado)


def bbox(geohash: str) -> tuple[float, float, float, float]:
    """Devuelve (lat_min, lat_max, lon_min, lon_max) de la celda."""

    lat_rango = [-90.0, 90.0]
    lon_rango = [-180.0, 180.0]
    par = True
    for caracter in geohash:
        valor = _DECODE[caracter]
        for desplazamiento in (4, 3, 2, 1, 0):
            bit = (valor >> desplazamiento) & 1
            rango = lon_rango if par else lat_rango
            medio = (rango[0] + rango[1]) / 2
            if bit:
                rango[0] = medio
            else:
                rango[1] = medio
            par = not par
    return lat_rango[0], lat_rango[1], lon_rango[0], lon_rango[1]


def poligono(geohash: str) -> dict:
    """Polígono GeoJSON (anillo cerrado, orden [lon, lat]) de la celda."""

    lat_min, lat_max, lon_min, lon_max = bbox(geohash)
    return {
        "type": "Polygon",
        "coordinates": [[
            [lon_min, lat_min],
            [lon_max, lat_min],
            [lon_max, lat_max],
            [lon_min, lat_max],
            [lon_min, lat_min],
        ]],
    }


def centro(geohash: str) -> dict:
    lat_min, lat_max, lon_min, lon_max = bbox(geohash)
    return {"type": "Point", "coordinates": [(lon_min + lon_max) / 2, (lat_min + lat_max) / 2]}
