"""Structured Streaming: modelo inmutable, upsert por review_id y ventanas de evento.

Dos queries independientes con checkpoints: inferencia/riesgo y ventanas sobre eventos
clasificados de Kafka. La salida Kafka puede repetirse tras un fallo, por eso la segunda
query deduplica review_id con el mismo watermark. Mongo usa claves deterministas.
"""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from kafka import KafkaProducer
from pyspark.ml import PipelineModel
from pyspark.sql import SparkSession, functions as F, types as T
from analitica import fecha_utc, variables, probabilidad
from comun import conectar, competidores, historial
import geohash


def guardar_ventanas(lote, batch_id):
    client, db = conectar()
    try:
        for fila in lote.orderBy("geohash", "window.start").toLocalIterator():
            r = fila.asDict(recursive=True)
            inicio, fin = r['window']['start'], r['window']['end']
            clave = f"{r['geohash']}|{inicio.isoformat()}"
            # Ventanas append: solo llegan cuando el watermark las cierra.
            anterior = db.live_windows.find_one({'geohash': r['geohash'], 'inicio': {'$lt': inicio}}, sort=[('inicio', -1)])
            pct = 100 * float(r['pct_neg'])
            salto = pct - anterior['pct_negativas'] if anterior else None
            umbral = float(os.getenv('HOTSPOT_UMBRAL_PP', '15'))
            minimo = int(os.getenv('HOTSPOT_MIN_RESENAS', '20'))
            doc = {'_id': clave, 'geohash': r['geohash'], 'inicio': inicio, 'fin': fin, 'n': r['n'],
                'pct_negativas': pct, 'salto_pp': salto, 'hotspot': bool(anterior and r['n'] >= minimo and anterior['n'] >= minimo and salto >= umbral),
                'location': geohash.poligono(r['geohash']), 'centro': geohash.centro(r['geohash']),
                'umbral_pp': umbral, 'min_resenas': minimo, 'batch_id': batch_id}
            db.live_windows.replace_one({'_id': clave}, doc, upsert=True)
        db.live_windows.create_index([('centro', '2dsphere')])
        db.live_windows.create_index([('location', '2dsphere')])
    finally:
        client.close()


def main():
    bootstrap = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092')
    topic = os.getenv('KAFKA_TOPIC', 'reviews')
    salida_topic = os.getenv('KAFKA_CLASSIFIED_TOPIC', 'reviews_classified')
    checkpoint = os.getenv('CHECKPOINT_DIR', '/checkpoints')
    modelo_path = Path(os.getenv('MODELO_PATH', '/models/sentimiento_v1'))
    metadata = json.loads((modelo_path / 'lifemap_metadata.json').read_text())
    corte = fecha_utc(os.getenv('FECHA_CORTE', '2019-01-01'))
    if not os.getenv('MONGO_DB', '').startswith('ci_') and metadata.get('fecha_corte') != corte.isoformat():
        raise ValueError('El modelo de sentimiento debe entrenarse con el mismo FECHA_CORTE antes del streaming.')
    version = metadata['version']
    riesgo = json.loads(Path(os.getenv('RIESGO_PATH', '/models/riesgo_v1.json')).read_text())
    if os.getenv('MANIFEST_PATH'):
        from versionado import comprobar_manifest
        manifest = comprobar_manifest(os.environ['MANIFEST_PATH'])
        if manifest['sentimiento']['ruta'] != str(modelo_path) or manifest['riesgo']['ruta'] != os.getenv('RIESGO_PATH', '/models/riesgo_v1.json'):
            raise ValueError('Las rutas no corresponden al manifiesto verificado')
    Path(checkpoint).mkdir(parents=True, exist_ok=True)
    archivo_version = Path(checkpoint) / 'model_versions.json'
    versiones = {'sentimiento': version, 'riesgo': riesgo['version'], 'corte': corte.isoformat()}
    if archivo_version.exists() and json.loads(archivo_version.read_text()) != versiones:
        raise ValueError('El checkpoint pertenece a otra versión de modelo/corte. Usar una nueva revisión de CHECKPOINT_DIR.')
    archivo_version.write_text(json.dumps(versiones))
    spark = (SparkSession.builder.master('local[2]').appName('lifemap-streaming')
        .config('spark.sql.shuffle.partitions', '3').config('spark.sql.session.timeZone', 'UTC').getOrCreate())
    spark.sparkContext.setLogLevel('WARN')
    modelo = PipelineModel.load(str(modelo_path))  # una sola carga, jamás fit en el flujo
    schema = T.StructType([T.StructField(n, T.StringType()) for n in ('review_id', 'business_id', 'texto', 'date', 'geohash')]
        + [T.StructField('estrellas', T.IntegerType())])

    def procesar(lote, batch_id):
        client, db = conectar()
        producer = KafkaProducer(bootstrap_servers=bootstrap, acks='all', retries=5,
            key_serializer=lambda x: x.encode(), value_serializer=lambda x: json.dumps(x).encode())
        try:
            afectados = set()
            for fila in modelo.transform(lote).select('review_id', 'business_id', 'texto', 'date', 'geohash', 'estrellas', 'prediction', 'probability').toLocalIterator():
                r = fila.asDict()
                fecha = fecha_utc(r['date'])
                if fecha <= corte:
                    continue
                doc = {'_id': r['review_id'], 'business_id': r['business_id'], 'texto': r['texto'], 'fecha': fecha,
                    'geohash': r['geohash'], 'estrellas': r['estrellas'], 'prediccion': int(r['prediction']),
                    'probabilidades': [float(x) for x in r['probability']], 'modelo_version': version,
                    'procesado_en': datetime.now(timezone.utc), 'batch_id': batch_id}
                db.reviews_live.replace_one({'_id': doc['_id']}, doc, upsert=True)
                # Solo publish después de guardar. Reintentos conservan review_id para deduplicación.
                producer.send(salida_topic, key=doc['business_id'], value={'review_id': doc['_id'],
                    'date': fecha.isoformat(), 'geohash': doc['geohash'], 'es_negativa': int(doc['prediccion'] == 0)}).get(timeout=30)
                afectados.add(doc['business_id'])
            producer.flush()
            for business_id in afectados:
                negocio = db.negocios.find_one({'_id': business_id})
                if not negocio:
                    continue
                ultimo = db.reviews_live.find_one({'business_id': business_id}, sort=[('fecha', -1)])['fecha']
                h = historial(db, business_id, ultimo, incluir_live=True, inicio_live=corte)
                v = variables(h, ultimo, negocio['primera_resena'], competidores(db, negocio, ultimo))
                p = probabilidad(riesgo, v)
                score = {'_id': business_id, 'location': negocio['location'], 'probabilidad': p,
                    'fecha': ultimo, 'variables': v, 'modelo_version': riesgo['version']}
                db.risk_scores.replace_one({'_id': business_id}, score, upsert=True)
                db.alerts.replace_one({'_id': business_id}, {**score, 'activa': p >= riesgo['umbral'],
                    'umbral': riesgo['umbral'], 'procesado_en': datetime.now(timezone.utc)}, upsert=True)
            for nombre in ('risk_scores', 'alerts'):
                db[nombre].create_index([('location', '2dsphere')])
            db.reviews_live.create_index([('business_id', 1), ('fecha', 1)])
            db.streaming_meta.replace_one({'_id': 'consumidor'}, {'_id': 'consumidor', 'batch_id': batch_id,
                'modelo_version': version, 'riesgo_version': riesgo['version'], 'actualizado_en': datetime.now(timezone.utc)}, upsert=True)
        finally:
            producer.close()
            client.close()

    def fuente(nombre):
        return (spark.readStream.format('kafka').option('kafka.bootstrap.servers', bootstrap)
            .option('subscribe', nombre).option('startingOffsets', 'earliest')
            .option('maxOffsetsPerTrigger', os.getenv('MAX_OFFSETS_PER_TRIGGER', '1000')).load())

    datos = fuente(topic).select(F.from_json(F.col('value').cast('string'), schema).alias('r')).select('r.*')
    validos = datos.filter('review_id IS NOT NULL AND business_id IS NOT NULL AND texto IS NOT NULL AND geohash IS NOT NULL AND estrellas BETWEEN 1 AND 5').filter(F.to_timestamp('date') > F.lit(corte))
    query = (validos.writeStream.foreachBatch(procesar).option('checkpointLocation', checkpoint + '/inferencia')
        .queryName('inferencia').trigger(processingTime='5 seconds').start())
    esquema_clasificado = 'review_id string, date string, geohash string, es_negativa int'
    clasificados = (fuente(salida_topic).select(F.from_json(F.col('value').cast('string'), esquema_clasificado).alias('r'))
        .select('r.*').withColumn('fecha', F.to_timestamp('date')).filter('fecha IS NOT NULL')
        .withWatermark('fecha', '7 days').dropDuplicatesWithinWatermark(['review_id']))
    ventanas = (clasificados.groupBy(F.window('fecha', '30 days'), 'geohash')
        .agg(F.count('*').alias('n'), F.avg('es_negativa').alias('pct_neg')))
    query_ventanas = (ventanas.writeStream.outputMode('append').foreachBatch(guardar_ventanas)
        .option('checkpointLocation', checkpoint + '/ventanas').queryName('ventanas').trigger(processingTime='5 seconds').start())
    import threading
    detener = threading.Event()
    def progreso():
        client, db = conectar()
        try:
            while not detener.wait(10):
                p = query.lastProgress
                if p and p.get('sources'):
                    offsets = p['sources'][0].get('endOffset') or {}
                    if isinstance(offsets, str):
                        offsets = json.loads(offsets)
                    db.streaming_meta.replace_one({'_id': 'progreso'}, {'_id': 'progreso',
                        'offsets': offsets.get(topic, {}), 'actualizado_en': datetime.fromisoformat(p['timestamp'].replace('Z', '+00:00'))}, upsert=True)
        finally:
            client.close()
    monitor = threading.Thread(target=progreso, daemon=True)
    monitor.start()
    try:
        spark.streams.awaitAnyTermination()
    finally:
        detener.set()
        monitor.join(timeout=15)
        query.stop()
        query_ventanas.stop()
        spark.stop()


if __name__ == '__main__':
    main()
