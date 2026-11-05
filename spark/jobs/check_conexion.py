"""
Prueba de integración Spark <-> MongoDB.

Lee negocios_semilla con el MongoDB Spark Connector, cuenta por categoría con los workers
del clúster y escribe el resultado en spark_check. Si esto funciona, el conector, las
credenciales y la red entre contenedores están bien.

Ejecutar:
  docker compose exec spark-master spark-submit /opt/jobs/check_conexion.py
"""
import sys

from pyspark.sql import functions as F

from comun import DB, crear_sesion

spark = crear_sesion("check-conexion-mongo")

df = (spark.read.format("mongodb")
      .option("database", DB).option("collection", "negocios_semilla").load())

total = df.count()
por_categoria = df.groupBy("categoria_principal").agg(F.count("*").alias("n")).orderBy("categoria_principal")
por_categoria.show(truncate=False)

(por_categoria.withColumn("calculado_en", F.current_timestamp())
 .write.format("mongodb").mode("overwrite")
 .option("database", DB).option("collection", "spark_check").save())

esperado = 100
print(f"[check] documentos leídos: {total} (esperado {esperado})")
spark.stop()
sys.exit(0 if total == esperado else 1)
