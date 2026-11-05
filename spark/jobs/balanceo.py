"""Balanceo de carga: tiempos con 2, 8, 32 y 200 particiones y filas por partición.

Mismo experimento de la Parte B del ejercicio de discos, sobre las reseñas de LifeMap:
- Operación medida: el MapReduce de reseñas negativas por clave (reduceByKey) con N
  particiones, R repeticiones por configuración (la lectura y el reparto no se cronometran).
- Sesgo: filas por partición con spark_partition_id(), comparando un reparto sin clave
  (round robin) con repartos por ciudad y por categoría principal.

Uso:
  spark-submit /opt/jobs/balanceo.py [--resenas resenas] [--particiones 2,8,32,200] [--repeticiones 3]
"""
import argparse
import csv
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from pyspark.sql import Row
from pyspark.sql import functions as F

from comun import crear_sesion, escribir, leer, prefijo_semilla


def medir(df, clave, particiones, repeticiones):
    filas = []
    for n in particiones:
        base = df.repartition(n).persist()
        base.count()  # materializa el reparto fuera del cronómetro
        for rep in range(1, repeticiones + 1):
            inicio = time.perf_counter()
            resultado = (base.select(clave, "negativa").rdd
                         .map(lambda r: (r[0], (int(r[1]), 1)))
                         .reduceByKey(lambda a, b: (a[0] + b[0], a[1] + b[1]), numPartitions=n)
                         .collect())
            segundos = time.perf_counter() - inicio
            filas.append({"particiones": n, "repeticion": rep, "segundos": round(segundos, 4),
                          "claves_resultado": len(resultado)})
            print(f"[balanceo] {n:>3} particiones, repetición {rep}: {segundos:.3f} s")
        base.unpersist()
    return filas


def resumir(filas):
    resumen = []
    for n in sorted({f["particiones"] for f in filas}):
        tiempos = [f["segundos"] for f in filas if f["particiones"] == n]
        resumen.append({
            "particiones": n, "repeticiones": len(tiempos),
            "media_s": round(statistics.mean(tiempos), 4),
            "desv_estandar_s": round(statistics.stdev(tiempos), 4) if len(tiempos) > 1 else 0.0,
            "min_s": min(tiempos), "max_s": max(tiempos),
        })
    return resumen


def distribucion(df, nombre, columna, n):
    repartido = df.repartition(n, F.col(columna)) if columna else df.repartition(n)
    conteos = {r["pid"]: r["filas"] for r in repartido.withColumn("pid", F.spark_partition_id())
               .groupBy("pid").agg(F.count("*").alias("filas")).collect()}
    valores = [conteos.get(i, 0) for i in range(n)]
    media = statistics.mean(valores)
    return (
        [{"reparto": nombre, "particion": i, "filas": v} for i, v in enumerate(valores)],
        {"reparto": nombre, "particiones": n, "min": min(valores), "max": max(valores),
         "media": round(media, 1), "desv_estandar": round(statistics.pstdev(valores), 1),
         "particiones_vacias": sum(1 for v in valores if v == 0),
         "max_sobre_media": round(max(valores) / media, 2) if media else None},
    )


def guardar_csv(ruta, filas):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=list(filas[0].keys()))
        escritor.writeheader()
        escritor.writerows(filas)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--resenas", default="resenas")
    p.add_argument("--clave", default="geohash", help="clave del MapReduce cronometrado")
    p.add_argument("--particiones", default="2,8,32,200")
    p.add_argument("--repeticiones", type=int, default=3)
    p.add_argument("--particiones-distribucion", type=int, default=32)
    p.add_argument("--evidencias", default="/data/evidencias")
    args = p.parse_args()
    particiones = [int(x) for x in args.particiones.split(",")]
    prefijo = prefijo_semilla(args.resenas)

    spark = crear_sesion("lifemap-balanceo")
    df = leer(spark, args.resenas, [{"$project": {
        "_id": 0, "geohash": 1, "ciudad": {"$ifNull": ["$ciudad", "DESCONOCIDA"]},
        "categoria_principal": 1, "negativa": 1}}]).persist()
    total = df.count()
    print(f"[balanceo] reseñas: {total:,}")

    tiempos = medir(df, args.clave, particiones, args.repeticiones)
    resumen = resumir(tiempos)
    detalle, estadisticas = [], []
    for nombre, columna in (("sin_clave", None), ("por_ciudad", "ciudad"),
                            ("por_categoria", "categoria_principal")):
        filas, stats = distribucion(df, nombre, columna, args.particiones_distribucion)
        detalle += filas
        estadisticas.append(stats)

    print("\n[balanceo] tiempos (media ± desviación):")
    for r in resumen:
        print(f"   {r['particiones']:>3} particiones: {r['media_s']:.3f} ± {r['desv_estandar_s']:.3f} s")
    print("\n[balanceo] filas por partición:")
    for s in estadisticas:
        print(f"   {s['reparto']:<14} min={s['min']:>8} max={s['max']:>8} media={s['media']:>10} "
              f"vacías={s['particiones_vacias']:>3} max/media={s['max_sobre_media']}")

    marca = datetime.now(timezone.utc).isoformat()
    for nombre, filas in (("balanceo_tiempos", tiempos), ("balanceo_resumen", resumen),
                          ("balanceo_distribucion", detalle), ("balanceo_estadisticas", estadisticas)):
        escribir(spark.createDataFrame([Row(**{**f, "registros": total, "calculado_en": marca}) for f in filas]),
                 f"{prefijo}{nombre}")
        guardar_csv(Path(args.evidencias) / f"{prefijo}{nombre}.csv", filas)
    print(f"\n[balanceo] CSV en {args.evidencias}")
    spark.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
