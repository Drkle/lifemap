"""Modelos sintéticos EXCLUSIVOS de integración: no son resultados académicos."""
import json
import os
from pathlib import Path
from pyspark.sql import SparkSession
from pyspark.ml import Pipeline
from pyspark.ml.feature import RegexTokenizer, HashingTF
from pyspark.ml.classification import NaiveBayes

spark = SparkSession.builder.master('local[2]').appName('fixture-smoke').config('spark.ui.enabled', 'false').getOrCreate()
spark.sparkContext.setLogLevel('ERROR')
filas = [(texto, float(label)) for _ in range(10) for texto, label in [('Terrible food and rude staff', 0), ('Average ordinary food', 1), ('Great food and friendly staff', 2)]]
modelo = Pipeline(stages=[RegexTokenizer(inputCol='texto', outputCol='tokens'),
    HashingTF(inputCol='tokens', outputCol='features', numFeatures=128),
    NaiveBayes(labelCol='etiqueta')]).fit(spark.createDataFrame(filas, 'texto string, etiqueta double'))
base = Path(os.getenv('MODELS_DIR', '/models'))
destino = base / 'sentimiento_v1'
modelo.write().overwrite().save(str(destino))
(destino / 'lifemap_metadata.json').write_text(json.dumps({'version': 'fixture-ci-1', 'modelo_activo': 'naive_bayes', 'fecha_corte': '2019-01-01T00:00:00'}))
features = ['sentimiento_medio', 'tendencia_negativa', 'estrellas', 'n_resenas', 'edad_dias', 'competidores_500m']
(base / 'riesgo_v1.json').write_text(json.dumps({'version': 'fixture-ci-1', 'features': features, 'media': [0]*6,
    'escala': [1]*6, 'coeficientes': [0]*6, 'intercepto': 0, 'umbral': .4, 'solo_fixture': True}))
spark.stop()
