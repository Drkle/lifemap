"""Modelo de sentimiento sobre el texto real de las reseñas (pipeline de SentimentStream).

Pipeline: RegexTokenizer -> StopWordsRemover (inglés) -> HashingTF -> IDF
Clasificadores comparados: Naive Bayes multinomial y regresión logística multinomial.

- Etiqueta: 1-2 estrellas = negativo (0), 3 = neutral (1), 4-5 = positivo (2).
- Partición SIN FUGA: por negocio (fold = |hash(business_id)| % 10; 0-7 entrenamiento,
  8-9 prueba). Un mismo negocio nunca queda en los dos lados; se verifica.
- Desbalance: la clase positiva domina. Con --balancear (por defecto) cada reseña de
  entrenamiento pesa n_total / (3 * n_clase); se reporta precision, recall y F1 por clase.
- Guarda los dos modelos y copia el de mayor F1 macro como el modelo activo
  (/models/sentimiento_v1), que usan /predict y la Entrega 2.

Uso:
  spark-submit /opt/jobs/sentimiento.py [--coleccion resenas] [--muestra 300000]
"""
import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from pyspark.ml import Pipeline, PipelineModel
from pyspark.ml.classification import LogisticRegression, NaiveBayes
from pyspark.ml.feature import HashingTF, IDF, RegexTokenizer, StopWordsRemover
from pyspark.sql import functions as F

import metricas
from comun import crear_sesion, leer, prefijo_semilla, registrar


def particion_por_negocio(df, folds_prueba=(8, 9)):
    df = df.withColumn("fold", F.abs(F.hash("business_id")) % 10)
    prueba = df.filter(F.col("fold").isin(*folds_prueba))
    entrenamiento = df.filter(~F.col("fold").isin(*folds_prueba))
    return entrenamiento, prueba


def con_pesos(df):
    conteos = {r["etiqueta"]: r["count"] for r in df.groupBy("etiqueta").count().collect()}
    total = sum(conteos.values())
    k = len(conteos)
    pesos = {c: total / (k * n) for c, n in conteos.items()}
    expr = F.create_map(*[x for c, w in pesos.items() for x in (F.lit(c), F.lit(float(w)))])
    return df.withColumn("peso", expr[F.col("etiqueta")]), pesos, conteos


def evaluar(predicciones):
    conteos = [(r["etiqueta"], int(r["prediction"]), r["count"])
               for r in predicciones.groupBy("etiqueta", "prediction").count().collect()]
    return metricas.desde_confusion(metricas.matriz(conteos))


def caracterizador(num_features):
    return Pipeline(stages=[
        RegexTokenizer(inputCol="texto", outputCol="tokens", pattern="[^a-z']+",
                       toLowercase=True, minTokenLength=2),
        StopWordsRemover(inputCol="tokens", outputCol="sin_stop",
                         stopWords=StopWordsRemover.loadDefaultStopWords("english")),
        HashingTF(inputCol="sin_stop", outputCol="tf", numFeatures=num_features),
        IDF(inputCol="tf", outputCol="features", minDocFreq=5),
    ])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--coleccion", default="resenas")
    p.add_argument("--muestra", type=int, default=300000, help="0 = todas las reseñas")
    p.add_argument("--num-features", type=int, default=1 << 18)
    p.add_argument("--salida", default="/models")
    p.add_argument("--balancear", default="true")
    p.add_argument("--semilla", type=int, default=42)
    p.add_argument("--fecha-corte", default="")
    p.add_argument("--nombre-modelo", choices=["sentimiento_v1", "sentimiento_e2_v1"], default="sentimiento_v1")
    args = p.parse_args()
    balancear = args.balancear.lower() == "true"
    prefijo = prefijo_semilla(args.coleccion)
    salida = Path(args.salida)
    nombre_activo = f"{prefijo}{args.nombre_modelo}"

    spark = crear_sesion("lifemap-sentimiento")
    pipeline_lectura = []
    fecha_corte = None
    if args.fecha_corte and not prefijo:
        corte_dt = datetime.fromisoformat(args.fecha_corte.replace("Z", "+00:00"))
        if corte_dt.tzinfo is not None:
            corte_dt = corte_dt.astimezone(timezone.utc).replace(tzinfo=None)
        fecha_corte = corte_dt.isoformat()
        pipeline_lectura.append({"$match": {"fecha": {"$lte": {"$date": fecha_corte + "Z"}}}})
    pipeline_lectura.append({"$project": {"_id": 0, "business_id": 1, "texto": 1, "etiqueta": 1}})
    df = leer(spark, args.coleccion, pipeline_lectura)
    total = df.count()
    if args.muestra and total > args.muestra:
        df = df.sample(withReplacement=False, fraction=args.muestra / total, seed=args.semilla)
    df = df.withColumn("etiqueta", F.col("etiqueta").cast("double")).cache()
    usadas = df.count()
    distribucion = {metricas.NOMBRES[int(r["etiqueta"])]: r["count"]
                    for r in df.groupBy("etiqueta").count().collect()}
    print(f"[sentimiento] reseñas en la colección={total:,} usadas={usadas:,} distribución={distribucion}")

    entrenamiento, prueba = particion_por_negocio(df)
    cruzados = (entrenamiento.select("business_id").distinct()
                .intersect(prueba.select("business_id").distinct()).count())
    if cruzados:
        raise SystemExit(f"Fuga: {cruzados} negocios en entrenamiento y prueba")
    if balancear:
        entrenamiento, pesos, _ = con_pesos(entrenamiento)
    else:
        entrenamiento, pesos = entrenamiento.withColumn("peso", F.lit(1.0)), {}

    feat = caracterizador(args.num_features).fit(entrenamiento)
    tr = feat.transform(entrenamiento).select("features", "etiqueta", "peso").cache()
    te = feat.transform(prueba).select("features", "etiqueta").cache()
    n_tr, n_te = tr.count(), te.count()
    print(f"[sentimiento] entrenamiento={n_tr:,} prueba={n_te:,} negocios cruzados={cruzados} pesos={pesos}")

    modelos = {
        "naive_bayes": NaiveBayes(featuresCol="features", labelCol="etiqueta", weightCol="peso",
                                  modelType="multinomial", smoothing=1.0),
        "regresion_logistica": LogisticRegression(featuresCol="features", labelCol="etiqueta",
                                                  weightCol="peso", family="multinomial",
                                                  maxIter=30, regParam=0.01),
    }
    resultados = {}
    for nombre, estimador in modelos.items():
        inicio = datetime.now(timezone.utc)
        ajustado = estimador.fit(tr)
        segundos = (datetime.now(timezone.utc) - inicio).total_seconds()
        m = evaluar(ajustado.transform(te))
        m["segundos_entrenamiento"] = round(segundos, 1)
        resultados[nombre] = m
        completo = PipelineModel(stages=feat.stages + [ajustado])
        completo.write().overwrite().save(str(salida / f"{prefijo}sentimiento_{nombre}"))
        print(f"[sentimiento] {nombre}: accuracy={m['accuracy']} f1_macro={m['f1_macro']}")
        for clase, v in m["por_clase"].items():
            print(f"      {clase:<9} precision={v['precision']:.3f} recall={v['recall']:.3f} "
                  f"f1={v['f1']:.3f} soporte={v['soporte']}")
        print(f"      matriz (filas=real, columnas=predicha): {m['matriz_confusion']['valores']}")

    mejor = max(resultados, key=lambda k: resultados[k]["f1_macro"])
    destino = salida / nombre_activo
    if destino.exists():
        shutil.rmtree(destino)
    shutil.copytree(salida / f"{prefijo}sentimiento_{mejor}", destino)
    version = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    resumen = {
        "_id": nombre_activo, "modelo_activo": mejor, "version": version,
        "fecha_corte": fecha_corte,
        "coleccion": args.coleccion, "resenas_coleccion": total, "resenas_usadas": usadas,
        "entrenamiento": n_tr, "prueba": n_te, "particion": "por negocio: |hash(business_id)| % 10 en {8,9} = prueba",
        "negocios_cruzados": cruzados, "balanceo_pesos": {metricas.NOMBRES[int(k)]: round(v, 4) for k, v in pesos.items()},
        "distribucion_etiquetas": distribucion, "num_features": args.num_features,
        "resultados": resultados, "calculado_en": datetime.now(timezone.utc).isoformat(),
    }
    (destino / "lifemap_metadata.json").write_text(json.dumps(resumen, indent=2, ensure_ascii=False))
    (salida / f"{prefijo}metricas_sentimiento.json").write_text(json.dumps(resumen, indent=2, ensure_ascii=False))
    registrar(spark, "modelo_metricas", {"_id": nombre_activo, "json": json.dumps(resumen, ensure_ascii=False),
                                         "modelo_activo": mejor, "version": version})
    print(f"[sentimiento] modelo activo: {mejor} -> {destino}")
    spark.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
