"""Tasas de cierre anualizadas por categoría principal y por celda de geohash.

1. Lee negocios (con su vida) y reseñas desde MongoDB con el conector.
2. MapReduce con RDD: (clave, (cierre, días_negocio, 1)) + reduceByKey, por categoría y por celda.
3. Valida que coincide con un groupBy de DataFrames; si no coincide, falla (y Jenkins no despliega).
4. % de reseñas negativas por celda, también con reduceByKey validado.
5. Guarda <prefijo>tasas_categoria, <prefijo>tasas_celda (con el polígono GeoJSON de la celda)
   y <prefijo>tasas_meta.

Uso:
  spark-submit /opt/jobs/tasas_mapreduce.py [--negocios negocios] [--resenas resenas] [--min-dias 18250]
"""
import argparse
import sys
from datetime import datetime, timezone

from pyspark.sql import Row

import geohash
from comun import crear_sesion, escribir, leer, prefijo_semilla, registrar
from mapreduce import (coinciden, con_tasa, groupby_cierres, groupby_negativas,
                       mapreduce_cierres, mapreduce_negativas)
from tasas import MIN_DIAS_NEGOCIO_DEFECTO, tasa_cierre


def geometria(gh):
    pol = geohash.poligono(gh)
    cen = geohash.centro(gh)
    return (Row(type="Polygon", coordinates=pol["coordinates"]),
            Row(type="Point", coordinates=cen["coordinates"]))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--negocios", default="negocios")
    p.add_argument("--resenas", default=None)
    p.add_argument("--min-dias", type=int, default=MIN_DIAS_NEGOCIO_DEFECTO)
    args = p.parse_args()
    resenas_col = args.resenas or args.negocios.replace("negocios", "resenas")
    prefijo = prefijo_semilla(args.negocios)

    spark = crear_sesion("lifemap-tasas-mapreduce")
    negocios = leer(spark, args.negocios, [{"$project": {
        "_id": 0, "business_id": "$_id", "categoria_principal": 1, "geohash": 1,
        "evento": 1, "dias_negocio": 1}}]).cache()
    resenas = leer(spark, resenas_col, [{"$project": {"_id": 0, "geohash": 1, "negativa": 1}}])

    n_negocios = negocios.count()
    print(f"[tasas] negocios leídos: {n_negocios}")

    resultados = {}
    for clave in ("categoria_principal", "geohash"):
        rdd_df = mapreduce_cierres(negocios, clave).cache()
        ok = coinciden(rdd_df, groupby_cierres(negocios, clave))
        print(f"[tasas] reduceByKey vs groupBy por {clave}: {'COINCIDEN' if ok else 'NO COINCIDEN'}")
        if not ok:
            raise SystemExit(f"MapReduce por {clave} no coincide con groupBy")
        resultados[clave] = [r.asDict() for r in rdd_df.collect()]

    neg_rdd = mapreduce_negativas(resenas, "geohash").cache()
    ok_neg = coinciden(neg_rdd, groupby_negativas(resenas, "geohash"))
    print(f"[tasas] negativas por celda reduceByKey vs groupBy: {'COINCIDEN' if ok_neg else 'NO COINCIDEN'}")
    if not ok_neg:
        raise SystemExit("Negativas por celda no coinciden con groupBy")
    negativas = {r["geohash"]: r.asDict() for r in neg_rdd.collect()}

    # ---- categorías
    categorias = con_tasa(resultados["categoria_principal"], args.min_dias)
    filas_cat = [Row(_id=c["categoria_principal"], categoria=c["categoria_principal"],
                     cierres=c["cierres"], dias_negocio=c["dias_negocio"], negocios=c["negocios"],
                     anios_negocio=c["anios_negocio"], tasa_cierre=c["tasa_cierre"],
                     cumple_minimo=c["cumple_minimo"]) for c in categorias]

    # ---- celdas (con % de negativas y geometría consultable)
    celdas = con_tasa(resultados["geohash"], args.min_dias)
    filas_celda = []
    for c in celdas:
        gh = c["geohash"]
        neg = negativas.get(gh, {"negativas": 0, "n_resenas": 0})
        poligono, centro = geometria(gh)
        filas_celda.append(Row(
            _id=gh, geohash=gh, cierres=c["cierres"], dias_negocio=c["dias_negocio"],
            negocios=c["negocios"], anios_negocio=c["anios_negocio"], tasa_cierre=c["tasa_cierre"],
            cumple_minimo=c["cumple_minimo"], n_resenas=neg["n_resenas"], negativas=neg["negativas"],
            pct_negativas=round(neg["negativas"] / neg["n_resenas"] * 100, 4) if neg["n_resenas"] else None,
            geometry=poligono, centro=centro))

    escribir(spark.createDataFrame(filas_cat), f"{prefijo}tasas_categoria")
    escribir(spark.createDataFrame(filas_celda), f"{prefijo}tasas_celda")

    total_cierres = sum(c["cierres"] for c in categorias)
    total_dias = sum(c["dias_negocio"] for c in categorias)
    meta = dict(
        _id="tasas", coleccion_negocios=args.negocios, min_dias_negocio=args.min_dias,
        negocios=n_negocios, categorias=len(filas_cat), celdas=len(filas_celda),
        categorias_sobre_minimo=sum(1 for c in categorias if c["cumple_minimo"]),
        celdas_sobre_minimo=sum(1 for c in celdas if c["cumple_minimo"]),
        cierres=total_cierres, dias_negocio=total_dias,
        tasa_global=round(tasa_cierre(total_cierres, total_dias) or 0, 4),
        validacion_rdd_vs_groupby=True, calculado_en=datetime.now(timezone.utc).isoformat())
    registrar(spark, f"{prefijo}tasas_meta", meta)
    print(f"[tasas] {meta}")

    top = sorted((c for c in categorias if c["cumple_minimo"]), key=lambda c: -(c["tasa_cierre"] or 0))[:10]
    print("[tasas] categorías con mayor tasa de cierre (sobre el mínimo):")
    for c in top:
        print(f"   {c['categoria_principal']:<30} tasa={c['tasa_cierre']:>7.3f}%  "
              f"cierres={c['cierres']:>5}  años-negocio={c['anios_negocio']:>9.1f}")
    spark.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
