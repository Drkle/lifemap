"""Utilidades compartidas por los jobs de Spark: sesión, lectura y escritura en MongoDB."""
import json
import os
from pathlib import Path
from urllib.parse import quote_plus

from pyspark.sql import Row, SparkSession

DB = os.getenv("MONGO_DB", "lifemap")
JOBS = Path(__file__).resolve().parent
# Módulos puros que también usan los executors (dentro de lambdas o UDF).
MODULOS_EXECUTORS = ("geohash.py", "tasas.py", "metricas.py", "mapreduce.py")


def mongo_uri():
    user = quote_plus(os.getenv("MONGO_ROOT_USER", ""))
    password = quote_plus(os.getenv("MONGO_ROOT_PASSWORD", ""))
    host = os.getenv("MONGO_HOST", "mongodb")
    port = os.getenv("MONGO_PORT", "27017")
    return f"mongodb://{user}:{password}@{host}:{port}/?authSource=admin"


def crear_sesion(nombre_app, master=None):
    uri = mongo_uri()
    spark = (
        SparkSession.builder.appName(nombre_app)
        .master(master or os.getenv("SPARK_MASTER_URL", "spark://spark-master:7077"))
        .config("spark.mongodb.read.connection.uri", uri)
        .config("spark.mongodb.write.connection.uri", uri)
        .config("spark.executor.memory", os.getenv("SPARK_EXECUTOR_MEMORY", "1200m"))
        .config("spark.sql.shuffle.partitions", os.getenv("SPARK_SHUFFLE_PARTITIONS", "8"))
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    for modulo in MODULOS_EXECUTORS:
        ruta = JOBS / modulo
        if ruta.exists():
            spark.sparkContext.addPyFile(str(ruta))
    return spark


def leer(spark, coleccion, pipeline=None):
    """Lee una colección con el MongoDB Spark Connector; el pipeline se ejecuta en MongoDB."""
    lector = (spark.read.format("mongodb")
              .option("database", DB).option("collection", coleccion))
    if pipeline:
        lector = lector.option("aggregation.pipeline", json.dumps(pipeline))
    return lector.load()


def escribir(df, coleccion):
    """Reemplaza la colección completa: cada ejecución deja resultados consistentes."""
    (df.write.format("mongodb").mode("overwrite")
     .option("database", DB).option("collection", coleccion).save())


def registrar(spark, coleccion, documento):
    """Guarda (o reemplaza por _id) un documento de metadatos."""
    (spark.createDataFrame([Row(**documento)]).write.format("mongodb").mode("append")
     .option("database", DB).option("collection", coleccion)
     .option("operationType", "replace").option("upsertDocument", "true").save())


def prefijo_semilla(coleccion):
    """negocios -> '' ; negocios_semilla -> 'semilla_'.

    La verificación sobre la semilla corre en cada build y nunca sobrescribe los
    resultados reales que consulta la API.
    """
    return "semilla_" if coleccion.endswith("_semilla") else ""
