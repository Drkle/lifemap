"""Reglas puras de limpieza y transformación del Yelp Open Dataset.

Todas las funciones reciben y devuelven DataFrames de pandas, así se prueban sin Dask ni
MongoDB. El pipeline las aplica partición por partición con Dask.

Negocios (business.json), en este orden:
  N1  coordenadas nulas o no numéricas
  N2  coordenadas fuera de rango o (0, 0)
  N3  fuera del área metropolitana del equipo (estado y, opcionalmente, caja de coordenadas)
  N4  sin la familia de categorías del equipo
  N5  is_open distinto de 0 o 1
  N6  business_id duplicado
  N7  sin ninguna reseña válida (se aplica después de procesar las reseñas)

Reseñas (review.json), en este orden:
  R1  el negocio no quedó en el conjunto limpio (otra área, otra familia o descartado)
  R2  texto nulo o vacío
  R3  estrellas fuera de 1..5
  R4  fecha nula o no interpretable
  R5  review_id duplicado (lo detecta el índice _id de MongoDB al cargar)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

import pandas as pd

import geohash

REGLAS_NEGOCIOS = (
    "N1_coord_nulas",
    "N2_coord_fuera_rango",
    "N3_fuera_area",
    "N4_sin_categoria",
    "N5_is_open_invalido",
    "N6_duplicado",
    "N7_sin_resenas",
)
REGLAS_RESENAS = (
    "R1_negocio_no_valido",
    "R2_texto_vacio",
    "R3_estrellas_invalidas",
    "R4_fecha_invalida",
    "R5_duplicado",
)

# Etiqueta de sentimiento derivada de las estrellas de la reseña (sección 4 del enunciado).
ETIQUETAS = {0: "negativo", 1: "neutral", 2: "positivo"}
GENERICAS = {"Restaurants", "Food"}
PRECISION_GEOHASH = 6


# ----------------------------------------------------------------------------- utilidades
def lista_categorias(texto: Any) -> list[str]:
    if texto is None or (isinstance(texto, float) and pd.isna(texto)):
        return []
    return [c.strip() for c in str(texto).split(",") if c.strip()]


def categoria_principal(categorias: Iterable[str], familia: str) -> str:
    """Primera categoría específica de la lista; si solo hay genéricas, la familia."""

    genericas = GENERICAS | {familia}
    for categoria in categorias:
        if categoria not in genericas:
            return categoria
    return familia


def etiqueta_desde_estrellas(estrellas: pd.Series) -> pd.Series:
    """1-2 -> 0 (negativo), 3 -> 1 (neutral), 4-5 -> 2 (positivo)."""

    return pd.cut(estrellas, bins=[0, 2, 3, 5], labels=[0, 1, 2]).astype("int64")


# ----------------------------------------------------------------------------- negocios
def limpiar_negocios(
    df: pd.DataFrame,
    *,
    estados: Iterable[str],
    familia: str,
    caja: tuple[float, float, float, float] | None = None,
    deduplicar: bool = True,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Aplica N1–N6 y devuelve los negocios normalizados con su reporte."""

    estados = {e.strip().upper() for e in estados if e.strip()}
    trabajo = df.copy()
    reporte = {"total_inicial": int(len(trabajo)), **{r: 0 for r in REGLAS_NEGOCIOS}}

    def eliminar(mascara: pd.Series, regla: str) -> None:
        nonlocal trabajo
        mascara = mascara.fillna(True).astype(bool)
        reporte[regla] += int(mascara.sum())
        trabajo = trabajo.loc[~mascara].copy()

    trabajo["_lat"] = pd.to_numeric(trabajo.get("latitude"), errors="coerce")
    trabajo["_lon"] = pd.to_numeric(trabajo.get("longitude"), errors="coerce")
    eliminar(trabajo["_lat"].isna() | trabajo["_lon"].isna(), "N1_coord_nulas")
    eliminar(
        ~trabajo["_lat"].between(-90, 90)
        | ~trabajo["_lon"].between(-180, 180)
        | ((trabajo["_lat"] == 0) & (trabajo["_lon"] == 0)),
        "N2_coord_fuera_rango",
    )

    fuera = ~trabajo["state"].astype("string").str.upper().isin(estados)
    if caja is not None:
        lat_min, lat_max, lon_min, lon_max = caja
        fuera = fuera | ~trabajo["_lat"].between(lat_min, lat_max) | ~trabajo["_lon"].between(lon_min, lon_max)
    eliminar(fuera, "N3_fuera_area")

    trabajo["_cats"] = trabajo["categories"].map(lista_categorias)
    eliminar(~trabajo["_cats"].map(lambda cats: familia in cats), "N4_sin_categoria")

    trabajo["_open"] = pd.to_numeric(trabajo["is_open"], errors="coerce")
    eliminar(~trabajo["_open"].isin([0, 1]), "N5_is_open_invalido")

    if deduplicar:
        eliminar(trabajo["business_id"].duplicated(keep="first"), "N6_duplicado")

    limpio = pd.DataFrame(
        {
            "business_id": trabajo["business_id"].astype(str),
            "nombre": trabajo["name"].astype("string").str.strip(),
            "ciudad": trabajo["city"].astype("string").str.strip(),
            "estado": trabajo["state"].astype("string").str.upper(),
            "latitude": trabajo["_lat"].astype("float64"),
            "longitude": trabajo["_lon"].astype("float64"),
            "estrellas": pd.to_numeric(trabajo["stars"], errors="coerce").astype("float64"),
            "review_count": pd.to_numeric(trabajo["review_count"], errors="coerce").fillna(0).astype("int64"),
            "is_open": trabajo["_open"].astype("int64"),
            "categorias": trabajo["_cats"],
            "categoria_principal": trabajo["_cats"].map(lambda c: categoria_principal(c, familia)),
        },
        index=trabajo.index,
    )
    limpio["geohash"] = [
        geohash.encode(lat, lon, PRECISION_GEOHASH)
        for lat, lon in zip(limpio["latitude"], limpio["longitude"])
    ]
    reporte["total_final"] = int(len(limpio))
    return limpio.reset_index(drop=True), reporte


# ----------------------------------------------------------------------------- reseñas
COLUMNAS_RESENA = ["review_id", "business_id", "stars", "text", "date"]


def limpiar_resenas(
    df: pd.DataFrame, negocios_validos: set[str] | dict[str, Any]
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Aplica R1–R4 (R5 se mide al cargar) y añade etiqueta, negativa y puntaje."""

    trabajo = df[COLUMNAS_RESENA].copy()
    reporte: dict[str, Any] = {"total_inicial": int(len(trabajo)), **{r: 0 for r in REGLAS_RESENAS}}

    # Fecha de corte del dataset: última fecha de reseña presente, medida ANTES de filtrar
    # por área, porque es una propiedad del dataset completo.
    fechas_todas = pd.to_datetime(trabajo["date"], errors="coerce", format="ISO8601")
    reporte["fecha_max"] = fechas_todas.max() if fechas_todas.notna().any() else None
    trabajo["_fecha"] = fechas_todas

    def eliminar(mascara: pd.Series, regla: str) -> None:
        nonlocal trabajo
        mascara = mascara.fillna(True).astype(bool)
        reporte[regla] += int(mascara.sum())
        trabajo = trabajo.loc[~mascara]

    validos = set(negocios_validos.keys() if isinstance(negocios_validos, dict) else negocios_validos)
    eliminar(~trabajo["business_id"].isin(validos), "R1_negocio_no_valido")
    texto = trabajo["text"].astype("string")
    eliminar(texto.isna() | (texto.str.strip() == ""), "R2_texto_vacio")
    estrellas = pd.to_numeric(trabajo["stars"], errors="coerce")
    eliminar(~estrellas.isin([1, 2, 3, 4, 5]), "R3_estrellas_invalidas")
    eliminar(trabajo["_fecha"].isna(), "R4_fecha_invalida")

    estrellas = pd.to_numeric(trabajo["stars"], errors="coerce").astype("int64")
    etiqueta = etiqueta_desde_estrellas(estrellas)
    limpio = pd.DataFrame(
        {
            "review_id": trabajo["review_id"].astype(str),
            "business_id": trabajo["business_id"].astype(str),
            "estrellas": estrellas,
            "texto": trabajo["text"].astype(str).str.strip(),
            "fecha": trabajo["_fecha"],
            "etiqueta": etiqueta,
            "negativa": (etiqueta == 0).astype("int64"),
            "puntaje": (etiqueta - 1).astype("int64"),  # -1 negativo, 0 neutral, +1 positivo
        }
    )
    reporte["total_final"] = int(len(limpio))
    reporte["por_etiqueta"] = {ETIQUETAS[k]: int(v) for k, v in etiqueta.value_counts().items()}
    return limpio.reset_index(drop=True), reporte


def agregar_por_negocio(resenas: pd.DataFrame) -> pd.DataFrame:
    """Agregado parcial por negocio (se combina entre particiones con combinar_agregados)."""

    if resenas.empty:
        return pd.DataFrame(
            {
                "business_id": pd.Series(dtype=str),
                "primera": pd.Series(dtype="datetime64[ns]"),
                "ultima": pd.Series(dtype="datetime64[ns]"),
                "n": pd.Series(dtype="int64"),
                "negativas": pd.Series(dtype="int64"),
                "suma_puntaje": pd.Series(dtype="int64"),
            }
        )
    return (
        resenas.groupby("business_id")
        .agg(
            primera=("fecha", "min"),
            ultima=("fecha", "max"),
            n=("review_id", "count"),
            negativas=("negativa", "sum"),
            suma_puntaje=("puntaje", "sum"),
        )
        .reset_index()
    )


def combinar_agregados(partes: list[pd.DataFrame]) -> pd.DataFrame:
    total = pd.concat(partes, ignore_index=True)
    return (
        total.groupby("business_id")
        .agg(
            primera=("primera", "min"),
            ultima=("ultima", "max"),
            n=("n", "sum"),
            negativas=("negativas", "sum"),
            suma_puntaje=("suma_puntaje", "sum"),
        )
        .reset_index()
    )


# ----------------------------------------------------------------------------- vida
def construir_vida(
    negocios: pd.DataFrame, agregados: pd.DataFrame, fecha_corte: datetime
) -> tuple[pd.DataFrame, int]:
    """Une negocios y agregados; calcula días-negocio, evento y censura.

    - Vida: de la primera a la última reseña, contando ambos días (un negocio con una
      sola reseña aporta 1 día-negocio). Es una aproximación: Yelp no trae fechas de
      apertura ni de cierre.
    - Evento: is_open = 0 es un cierre observado.
    - Censura: is_open = 1; solo se sabe que seguía abierto en la fecha de corte.
    Devuelve el DataFrame y cuántos negocios se descartaron por N7 (sin reseñas válidas).
    """

    unidos = negocios.merge(agregados, on="business_id", how="left")
    sin_resenas = unidos["n"].isna()
    unidos = unidos.loc[~sin_resenas].copy()
    primera = pd.to_datetime(unidos["primera"]).dt.normalize()
    ultima = pd.to_datetime(unidos["ultima"]).dt.normalize()
    unidos["primera_resena"] = primera
    unidos["ultima_resena"] = ultima
    unidos["n_resenas"] = unidos["n"].astype("int64")
    unidos["dias_negocio"] = ((ultima - primera).dt.days + 1).astype("int64")
    unidos["evento"] = (unidos["is_open"] == 0).astype("int64")
    unidos["censurado"] = unidos["is_open"] == 1
    unidos["dias_hasta_corte"] = ((pd.Timestamp(fecha_corte).normalize() - primera).dt.days + 1).astype("int64")
    unidos["pct_negativas"] = (unidos["negativas"] / unidos["n"] * 100).astype("float64")
    unidos["sentimiento_medio"] = (unidos["suma_puntaje"] / unidos["n"]).astype("float64")
    unidos = unidos.drop(columns=["primera", "ultima", "n", "suma_puntaje"])
    unidos["negativas"] = unidos["negativas"].astype("int64")
    return unidos.reset_index(drop=True), int(sin_resenas.sum())


# ----------------------------------------------------------------------------- documentos
def _fecha(valor: Any) -> datetime:
    if isinstance(valor, pd.Timestamp):
        return valor.to_pydatetime()
    return valor


def documento_negocio(fila: dict[str, Any], fecha_corte: datetime) -> dict[str, Any]:
    """Documento GeoJSON del negocio con su vida, listo para MongoDB."""

    return {
        "_id": fila["business_id"],
        "nombre": None if pd.isna(fila["nombre"]) else str(fila["nombre"]),
        "ciudad": None if pd.isna(fila["ciudad"]) else str(fila["ciudad"]),
        "estado": str(fila["estado"]),
        "location": {"type": "Point", "coordinates": [float(fila["longitude"]), float(fila["latitude"])]},
        "geohash": fila["geohash"],
        "estrellas": None if pd.isna(fila["estrellas"]) else float(fila["estrellas"]),
        "review_count_yelp": int(fila["review_count"]),
        "is_open": int(fila["is_open"]),
        "categorias": list(fila["categorias"]),
        "categoria_principal": fila["categoria_principal"],
        "primera_resena": _fecha(fila["primera_resena"]),
        "ultima_resena": _fecha(fila["ultima_resena"]),
        "n_resenas": int(fila["n_resenas"]),
        "dias_negocio": int(fila["dias_negocio"]),
        "evento": int(fila["evento"]),
        "censurado": bool(fila["censurado"]),
        "dias_hasta_corte": int(fila["dias_hasta_corte"]),
        "fecha_corte": fecha_corte,
        "negativas": int(fila["negativas"]),
        "pct_negativas": float(fila["pct_negativas"]),
        "sentimiento_medio": float(fila["sentimiento_medio"]),
    }


def documento_resena(fila: dict[str, Any], negocio: dict[str, Any]) -> dict[str, Any]:
    """Reseña que referencia a su negocio; se copian geohash y categoría para agregar sin join."""

    return {
        "_id": fila["review_id"],
        "business_id": fila["business_id"],
        "estrellas": int(fila["estrellas"]),
        "texto": fila["texto"],
        "fecha": _fecha(fila["fecha"]),
        "etiqueta": int(fila["etiqueta"]),
        "sentimiento": ETIQUETAS[int(fila["etiqueta"])],
        "negativa": int(fila["negativa"]),
        "geohash": negocio["geohash"],
        "categoria_principal": negocio["categoria_principal"],
        "ciudad": negocio["ciudad"],
    }
