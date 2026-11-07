"""Pipeline distribuido e idempotente: Kaggle (Yelp) -> Dask -> MongoDB.

Pasos:
  1. Descarga business.json y review.json con la API de Kaggle (caché en el volumen /data).
  2. Lee business.json particionado con Dask y aplica N1–N6.
  3. Lee review.json particionado (bloques de REVIEW_BLOCKSIZE) y, partición por partición,
     aplica R1–R4, carga las reseñas por lotes en MongoDB (R5 lo mide el índice _id) y
     devuelve conteos de limpieza. Los agregados por negocio salen de los documentos únicos en MongoDB.
  4. Agrega las reseñas únicas persistidas en MongoDB: vida de cada negocio (primera/última reseña, días-negocio,
     evento, censura), sentimiento medio y % de negativas; aplica N7.
  5. Carga los negocios como GeoJSON por lotes y crea los índices (2dsphere incluido).
  6. Guarda el reporte con los conteos antes/después de cada regla.

Variables de entorno principales (ver .env.example):
  LIFEMAP_ESTADOS, LIFEMAP_CATEGORIA, LIFEMAP_CAJA, INGEST_MAX_PARTICIONES, FORCE_RELOAD
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

import dask
import dask.dataframe as dd
import pandas as pd
from dask import delayed
from distributed import Client
from pymongo import ASCENDING, GEOSPHERE, MongoClient, UpdateOne
from pymongo.errors import BulkWriteError

import limpieza
from descarga import descargar_dataset


def _verdadero(nombre: str) -> bool:
    return os.getenv(nombre, "false").lower() in {"1", "true", "yes", "si", "sí"}


def _mongo_uri() -> str:
    usuario = quote_plus(os.getenv("MONGO_ROOT_USER", "admin"))
    clave = quote_plus(os.environ["MONGO_ROOT_PASSWORD"])
    host = os.getenv("MONGO_HOST", "mongodb")
    puerto = os.getenv("MONGO_PORT", "27017")
    return f"mongodb://{usuario}:{clave}@{host}:{puerto}/?authSource=admin"


def _caja() -> tuple[float, float, float, float] | None:
    texto = os.getenv("LIFEMAP_CAJA", "").strip()
    if not texto:
        return None
    valores = tuple(float(v) for v in texto.split(","))
    if len(valores) != 4:
        raise ValueError("LIFEMAP_CAJA debe ser lat_min,lat_max,lon_min,lon_max")
    return valores  # type: ignore[return-value]


def _sumar(reportes: list[dict], reglas: tuple[str, ...]) -> dict:
    total = {"total_inicial": 0, **{r: 0 for r in reglas}, "total_final": 0}
    for reporte in reportes:
        for clave in total:
            total[clave] += int(reporte.get(clave, 0))
    return total


# ----------------------------------------------------------------------------- reseñas
def procesar_particion_resenas(
    particion: pd.DataFrame,
    info_negocios: dict[str, dict],
    uri: str,
    base: str,
    coleccion: str,
    tamano_lote: int,
) -> dict:
    """Carga idempotente: repetir una tarea no cambia sus conteos ni elimina reseñas.

    El reporte cuenta filas de entrada limpias. R5 se calcula globalmente al terminar,
    comparando esas filas con los review_id únicos realmente persistidos en MongoDB.
    """
    limpio, reporte = limpieza.limpiar_resenas(particion, info_negocios)
    if not limpio.empty:
        cliente = MongoClient(uri)
        destino = cliente[base][coleccion]
        try:
            registros = limpio.drop_duplicates("review_id", keep="first").to_dict("records")
            for inicio in range(0, len(registros), tamano_lote):
                documentos = [limpieza.documento_resena(r, info_negocios[r["business_id"]])
                              for r in registros[inicio:inicio + tamano_lote]]
                operaciones = [UpdateOne({"_id": d["_id"]}, {"$setOnInsert": d}, upsert=True)
                               for d in documentos]
                try:
                    destino.bulk_write(operaciones, ordered=False)
                except BulkWriteError as error:
                    # Dos tareas pueden intentar crear el mismo _id simultáneamente.
                    detalles = error.details
                    if detalles.get("writeConcernErrors") or any(e.get("code") != 11000 for e in detalles.get("writeErrors", [])):
                        raise
                    for fallo in detalles.get("writeErrors", []):
                        d = documentos[fallo["index"]]
                        destino.update_one({"_id": d["_id"]}, {"$setOnInsert": d}, upsert=True)
        finally:
            cliente.close()
    return reporte


def agregar_resenas_persistidas(coleccion) -> tuple[pd.DataFrame, int]:
    """Una sola fuente de verdad para vida/conteos, incluso si Dask repite tareas."""
    filas = list(coleccion.aggregate([
        {"$group": {"_id": "$business_id", "primera": {"$min": "$fecha"},
                    "ultima": {"$max": "$fecha"}, "n": {"$sum": 1},
                    "negativas": {"$sum": "$negativa"},
                    "suma_puntaje": {"$sum": {"$subtract": ["$etiqueta", 1]}}}},
        {"$project": {"_id": 0, "business_id": "$_id", "primera": 1, "ultima": 1,
                      "n": 1, "negativas": 1, "suma_puntaje": 1}},
    ], allowDiskUse=True))
    agregado = pd.DataFrame(filas, columns=["business_id", "primera", "ultima", "n", "negativas", "suma_puntaje"])
    total = int(agregado["n"].sum()) if filas else 0
    return agregado, total


def finalizar_reporte_resenas(reportes, total_persistido):
    reporte = _sumar(reportes, limpieza.REGLAS_RESENAS)
    duplicadas = reporte["total_final"] - total_persistido
    if duplicadas < 0:
        raise RuntimeError("MongoDB contiene más reseñas que las procesadas: revisar ejecuciones concurrentes.")
    reporte["R5_duplicado"] = duplicadas
    reporte["total_final"] = total_persistido
    return reporte


def _insertar_lotes(destino, documentos: list[dict], tamano_lote: int) -> int:
    insertados = 0
    for inicio in range(0, len(documentos), tamano_lote):
        resultado = destino.insert_many(documentos[inicio : inicio + tamano_lote], ordered=False)
        insertados += len(resultado.inserted_ids)
    return insertados


def calcular_por_bloques(cliente, tareas, max_en_vuelo=2):
    """Acota el grafo activo y la presión de memoria; conserva reportes, no textos."""
    if max_en_vuelo < 1:
        raise ValueError("INGEST_MAX_EN_VUELO debe ser al menos 1")
    resultados = []
    for inicio in range(0, len(tareas), max_en_vuelo):
        futuros = cliente.compute(tareas[inicio:inicio + max_en_vuelo], retries=2)
        try:
            resultados.extend(cliente.gather(futuros))
        finally:
            for futuro in futuros:
                futuro.release()
        print(f"[ingesta] progreso: {len(resultados)}/{len(tareas)} particiones completadas", flush=True)
    return resultados


# ----------------------------------------------------------------------------- principal
def ejecutar() -> None:
    inicio = time.perf_counter()
    dataset = os.getenv("KAGGLE_DATASET", "yelp-dataset/yelp-dataset")
    estados = [e for e in os.getenv("LIFEMAP_ESTADOS", "FL").split(",") if e.strip()]
    familia = os.getenv("LIFEMAP_CATEGORIA", "Restaurants").strip()
    caja = _caja()
    max_particiones = int(os.getenv("INGEST_MAX_PARTICIONES", "0"))
    tamano_lote = int(os.getenv("INGEST_BATCH_SIZE", "5000"))
    blocksize = os.getenv("REVIEW_BLOCKSIZE", "16MB")
    max_en_vuelo = int(os.getenv("INGEST_MAX_EN_VUELO", "2"))
    forzar = _verdadero("FORCE_RELOAD")
    base = os.getenv("MONGO_DB", "lifemap")
    col_negocios = os.getenv("NEGOCIOS_COLLECTION", "negocios")
    col_resenas = os.getenv("RESENAS_COLLECTION", "resenas")
    clave_meta = f"{dataset}|{','.join(estados)}|{familia}|{caja}|max_part={max_particiones}"
    uri = _mongo_uri()

    mongo = MongoClient(uri)
    db = mongo[base]
    meta = db["ingesta_meta"].find_one({"_id": clave_meta, "estado": "completa"})
    if (
        meta
        and not forzar
        and db[col_negocios].count_documents({}) == meta.get("negocios", {}).get("total_final")
        and db[col_resenas].count_documents({}) == meta.get("resenas", {}).get("total_final")
    ):
        print(f"[ingesta] Ingesta omitida: los datos ya corresponden a {clave_meta}.")
        mongo.close()
        return

    db["ingesta_meta"].update_one(
        {"_id": clave_meta},
        {"$set": {"estado": "en_progreso", "inicio": datetime.now(timezone.utc)}},
        upsert=True,
    )

    cliente_dask: Client | None = None
    try:
        rutas = descargar_dataset(dataset)
        cliente_dask = Client(os.getenv("DASK_SCHEDULER", "tcp://dask-scheduler:8786"))
        cliente_dask.wait_for_workers(2, timeout=120)
        # dask scheduler/worker no tienen /opt/ingest en sys.path: se suben los módulos.
        for modulo in ("geohash.py", "limpieza.py"):
            cliente_dask.upload_file(str(Path(__file__).with_name(modulo)))
        print(f"[ingesta] workers: {len(cliente_dask.scheduler_info()['workers'])}")

        # ---- 1. Negocios: lectura particionada + N1..N6
        raw_neg = dd.read_json(str(rutas["business"]), lines=True, blocksize="16MB")
        print(f"[ingesta] business.json en {raw_neg.npartitions} particiones")
        partes = [
            delayed(limpieza.limpiar_negocios)(p, estados=estados, familia=familia, caja=caja, deduplicar=False)
            for p in raw_neg.to_delayed()
        ]
        resultados = dask.compute(*partes)
        negocios = pd.concat([r[0] for r in resultados], ignore_index=True)
        rep_neg = _sumar([r[1] for r in resultados], limpieza.REGLAS_NEGOCIOS)
        duplicados = negocios["business_id"].duplicated(keep="first")
        rep_neg["N6_duplicado"] = int(duplicados.sum())
        negocios = negocios.loc[~duplicados].reset_index(drop=True)
        print(f"[ingesta] negocios en el área y familia: {len(negocios):,}")
        if negocios.empty:
            raise RuntimeError("Ningún negocio cumple el área y la familia configuradas.")

        info = {
            fila.business_id: {
                "geohash": fila.geohash,
                "categoria_principal": fila.categoria_principal,
                "ciudad": None if pd.isna(fila.ciudad) else str(fila.ciudad),
            }
            for fila in negocios.itertuples()
        }
        # El diccionario va como argumento del grafo, no como Future de scatter.
        # Así Dask puede reconstruir la tarea si se pierden/reinician sus workers.

        # ---- 2. Reseñas: lectura particionada, limpieza y carga por lotes en un solo paso
        for coleccion in (col_resenas, col_negocios):
            db[coleccion].delete_many({})
        raw_res = dd.read_json(str(rutas["review"]), lines=True, blocksize=blocksize)
        particiones = raw_res.to_delayed()
        if max_particiones > 0:
            particiones = particiones[:max_particiones]
        print(f"[ingesta] review.json en {raw_res.npartitions} particiones (se procesan {len(particiones)})")
        tareas = [
            delayed(procesar_particion_resenas)(p, info, uri, base, col_resenas, tamano_lote)
            for p in particiones
        ]
        reportes_res = calcular_por_bloques(cliente_dask, tareas, max_en_vuelo)
        agregados, total_persistido = agregar_resenas_persistidas(db[col_resenas])
        rep_res = finalizar_reporte_resenas(reportes_res, total_persistido)
        if total_persistido == 0:
            raise RuntimeError("No se guardaron reseñas válidas para el área seleccionada.")
        print(f"[ingesta] reseñas únicas persistidas: {total_persistido:,}; duplicados de origen: {rep_res['R5_duplicado']:,}")
        por_etiqueta: dict[str, int] = {}
        for reporte in reportes_res:
            for clave, valor in reporte.get("por_etiqueta", {}).items():
                por_etiqueta[clave] = por_etiqueta.get(clave, 0) + valor
        rep_res["por_etiqueta_antes_R5"] = por_etiqueta
        fechas = [r["fecha_max"] for r in reportes_res if r.get("fecha_max") is not None]
        fecha_corte = pd.Timestamp(max(fechas)).to_pydatetime()

        # ---- 3. Vida de cada negocio + N7
        negocios_vida, sin_resenas = limpieza.construir_vida(negocios, agregados, fecha_corte)
        rep_neg["N7_sin_resenas"] = sin_resenas
        rep_neg["total_final"] = int(len(negocios_vida))
        documentos = [limpieza.documento_negocio(f, fecha_corte) for f in negocios_vida.to_dict("records")]
        destino = db[col_negocios]
        if "location_2dsphere" in destino.index_information():
            destino.drop_index("location_2dsphere")
        insertados = _insertar_lotes(destino, documentos, tamano_lote)
        destino.create_index([("location", GEOSPHERE)], name="location_2dsphere")
        destino.create_index([("categoria_principal", ASCENDING)], name="categoria_principal_1")
        destino.create_index([("geohash", ASCENDING)], name="geohash_1")

        resenas = db[col_resenas]
        resenas.create_index([("business_id", ASCENDING)], name="business_id_1")
        resenas.create_index([("fecha", ASCENDING)], name="fecha_1")
        resenas.create_index([("geohash", ASCENDING)], name="geohash_1")

        total_resenas = resenas.count_documents({})
        if insertados != rep_neg["total_final"] or total_resenas != rep_res["total_final"]:
            raise RuntimeError(
                f"Conteos inconsistentes: negocios {insertados}/{rep_neg['total_final']}, "
                f"reseñas {total_resenas}/{rep_res['total_final']}"
            )

        cierres = int(negocios_vida["evento"].sum())
        evidencia = {
            "dataset": dataset,
            "area_estados": estados,
            "familia": familia,
            "caja": caja,
            "particiones_business": raw_neg.npartitions,
            "particiones_review": raw_res.npartitions,
            "particiones_procesadas": len(particiones),
            "fecha_corte": fecha_corte.isoformat(),
            "negocios": rep_neg,
            "resenas": rep_res,
            "vida": {
                "cierres_observados": cierres,
                "censurados": int(len(negocios_vida) - cierres),
                "dias_negocio_total": int(negocios_vida["dias_negocio"].sum()),
                "dias_negocio_mediana": float(negocios_vida["dias_negocio"].median()),
                "negocios_con_una_resena": int((negocios_vida["n_resenas"] == 1).sum()),
            },
            "duracion_segundos": round(time.perf_counter() - inicio, 1),
            "fecha_utc": datetime.now(timezone.utc).isoformat(),
        }
        Path("/data/reporte_limpieza.json").write_text(
            json.dumps(evidencia, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
        )
        db["ingesta_meta"].update_one(
            {"_id": clave_meta},
            {"$set": {**evidencia, "estado": "completa", "fin": datetime.now(timezone.utc)}},
            upsert=True,
        )
        print(json.dumps(evidencia, indent=2, ensure_ascii=False, default=str))
        print(f"[ingesta] COMPLETA en {evidencia['duracion_segundos']} s")
    except Exception as exc:
        db["ingesta_meta"].update_one(
            {"_id": clave_meta},
            {"$set": {"estado": "error", "error": str(exc)[:500], "fin": datetime.now(timezone.utc)}},
            upsert=True,
        )
        try:
            db[col_negocios].create_index([("location", GEOSPHERE)], name="location_2dsphere")
        except Exception:
            pass
        raise
    finally:
        if cliente_dask is not None:
            cliente_dask.close()
        mongo.close()


if __name__ == "__main__":
    ejecutar()
