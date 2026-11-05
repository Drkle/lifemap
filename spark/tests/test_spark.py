"""Pruebas de la lógica de Spark sin MongoDB (Spark local).

Jenkins las ejecuta con:
  docker run --rm bdgeo-spark spark-submit --master local[2] /opt/tests/test_spark.py
Sale con código 1 si alguna falla, lo que detiene el pipeline.
"""
import math
import os
import sys
import traceback

JOBS = os.environ.get("LIFEMAP_JOBS", "/opt/jobs")
sys.path.insert(0, JOBS)

from pyspark.sql import SparkSession  # noqa: E402

import geohash  # noqa: E402
import metricas  # noqa: E402
from mapreduce import (coinciden, con_tasa, groupby_cierres, groupby_negativas,  # noqa: E402
                       mapreduce_cierres, mapreduce_negativas)
from tasas import MIN_DIAS_NEGOCIO_DEFECTO, tasa_cierre  # noqa: E402

spark = (SparkSession.builder.master(os.environ.get("SPARK_TEST_MASTER", "local[2]"))
         .appName("lifemap-tests").config("spark.sql.shuffle.partitions", "4").getOrCreate())
spark.sparkContext.setLogLevel("ERROR")
for modulo in ("geohash.py", "tasas.py", "metricas.py", "mapreduce.py"):
    spark.sparkContext.addPyFile(os.path.join(JOBS, modulo))


def test_formula_tasa_cierre():
    # 3 cierres en 100 años-negocio = 3 % anual (misma fórmula que la AFR de discos)
    assert math.isclose(tasa_cierre(3, 36500), 3.0)
    assert math.isclose(tasa_cierre(1, 365), 100.0)
    assert tasa_cierre(0, 0) is None
    assert tasa_cierre(0, 1000) == 0.0
    try:
        tasa_cierre(-1, 10)
        raise AssertionError("debía rechazar cierres negativos")
    except ValueError:
        pass
    assert MIN_DIAS_NEGOCIO_DEFECTO == 50 * 365


def test_tasa_no_es_proporcion_de_cerrados():
    # 1 de 2 negocios cerrado (50 %), pero con 730 días-negocio la tasa anual es 50 %;
    # con 7300 días-negocio baja a 5 %: la proporción simple no cambia, la tasa sí.
    assert math.isclose(tasa_cierre(1, 730), 50.0)
    assert math.isclose(tasa_cierre(1, 7300), 5.0)


def _negocios():
    filas = []
    for i in range(100):
        filas.append((f"n{i}", "Pizza" if i % 2 == 0 else "Mexican",
                      "dhvqgx" if i < 60 else "dhvr59",
                      1 if (i % 5 == 0 or (i % 2 == 0 and i % 5 == 1)) else 0,
                      365 * (1 + i % 5)))
    return spark.createDataFrame(filas, "business_id string, categoria_principal string, "
                                        "geohash string, evento int, dias_negocio int")


def test_mapreduce_coincide_con_groupby():
    df = _negocios()
    for clave in ("categoria_principal", "geohash"):
        assert coinciden(mapreduce_cierres(df, clave), groupby_cierres(df, clave)), clave
    filas = {r["categoria_principal"]: r.asDict() for r in mapreduce_cierres(df, "categoria_principal").collect()}
    assert filas["Pizza"]["cierres"] == 20 and filas["Pizza"]["dias_negocio"] == 54750
    assert filas["Mexican"]["cierres"] == 10 and filas["Mexican"]["negocios"] == 50
    tasas = {f["categoria_principal"]: f for f in con_tasa(list(filas.values()), 18250)}
    assert math.isclose(tasas["Pizza"]["tasa_cierre"], 13.3333, abs_tol=1e-4)
    assert tasas["Pizza"]["cumple_minimo"] is True
    assert con_tasa([{"cierres": 1, "dias_negocio": 100}], 18250)[0]["cumple_minimo"] is False


def test_coinciden_detecta_diferencias():
    a = spark.createDataFrame([("x", 1)], "k string, v int")
    b = spark.createDataFrame([("x", 2)], "k string, v int")
    assert not coinciden(a, b)


def test_negativas_por_celda():
    df = spark.createDataFrame([("a", 1), ("a", 0), ("a", 0), ("b", 1)], "geohash string, negativa int")
    assert coinciden(mapreduce_negativas(df, "geohash"), groupby_negativas(df, "geohash"))
    r = {x["geohash"]: x for x in mapreduce_negativas(df, "geohash").collect()}
    assert r["a"]["negativas"] == 1 and r["a"]["n_resenas"] == 3


def test_metricas_desde_confusion():
    m = metricas.matriz([(0, 0, 8), (0, 2, 2), (1, 1, 1), (1, 2, 4), (2, 2, 80), (2, 0, 5)])
    r = metricas.desde_confusion(m)
    assert r["total"] == 100
    assert math.isclose(r["accuracy"], 0.89)
    neg = r["por_clase"]["negativo"]
    assert math.isclose(neg["precision"], round(8 / 13, 4)) and math.isclose(neg["recall"], 0.8)
    assert r["por_clase"]["neutral"]["soporte"] == 5


def test_geohash():
    assert geohash.encode(57.64911, 10.40744, 11) == "u4pruydqqvj"
    assert geohash.encode(27.9460, -82.4620, 6) == "dhvqgx"


def test_particion_por_negocio_sin_fuga():
    from sentimiento import particion_por_negocio
    filas = [(f"b{i % 37}", "great food" if i % 3 else "awful service", float(2 if i % 3 else 0))
             for i in range(600)]
    df = spark.createDataFrame(filas, "business_id string, texto string, etiqueta double")
    tr, te = particion_por_negocio(df)
    cruzados = tr.select("business_id").distinct().intersect(te.select("business_id").distinct()).count()
    assert cruzados == 0
    assert tr.count() + te.count() == 600 and te.count() > 0


def test_pipeline_sentimiento_entrena_y_predice():
    from pyspark.ml.classification import NaiveBayes
    from sentimiento import caracterizador, con_pesos
    positivos = ["great food friendly staff", "amazing pizza loved it", "excellent tacos great service"]
    negativos = ["terrible service cold food", "awful rude waiter", "dirty tables bad food"]
    neutrales = ["average place okay prices", "decent nothing special okay"]
    filas = ([(t, 2.0) for t in positivos * 20] + [(t, 0.0) for t in negativos * 6]
             + [(t, 1.0) for t in neutrales * 5])
    df = spark.createDataFrame(filas, "texto string, etiqueta double")
    df, pesos, conteos = con_pesos(df)
    assert conteos[2.0] == 60 and conteos[0.0] == 18
    assert pesos[0.0] > pesos[2.0]  # la clase minoritaria pesa más
    feat = caracterizador(1 << 10).fit(df)
    modelo = NaiveBayes(labelCol="etiqueta", weightCol="peso").fit(feat.transform(df))
    prueba = spark.createDataFrame([("the food was terrible and cold",), ("great friendly pizza",),
                                    ("okay average place",)], "texto string")
    pred = [r["prediction"] for r in modelo.transform(feat.transform(prueba)).collect()]
    assert pred == [0.0, 2.0, 1.0], pred


if __name__ == "__main__":
    pruebas = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    fallidas = 0
    for nombre, funcion in pruebas:
        try:
            funcion()
            print(f"PASS {nombre}")
        except Exception:  # noqa: BLE001
            fallidas += 1
            print(f"FAIL {nombre}")
            traceback.print_exc()
    spark.stop()
    print(f"\n{len(pruebas) - fallidas}/{len(pruebas)} pruebas de Spark aprobadas")
    sys.exit(1 if fallidas else 0)
