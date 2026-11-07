"""Prueba aislada: 100 mensajes reales por Spark, modelo versionado y reenvío idempotente.

Usar un topic, una base y checkpoints exclusivos de CI. El consumidor se ejecuta con
esas mismas variables. Nunca publica mensajes de prueba al topic de producción.
"""
import argparse
import json
import os
import time
import uuid
from pathlib import Path
from datetime import timedelta
from kafka import KafkaProducer, KafkaConsumer, TopicPartition
from analitica import fecha_utc
from comun import conectar


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--timeout', type=int, default=240)
    args = p.parse_args()
    topic = os.environ['KAFKA_TOPIC']
    if not topic.startswith('ci_') or not os.getenv('MONGO_DB', '').startswith('ci_'):
        raise SystemExit('Smoke exige topic y base ci_ para no contaminar producción.')
    client, db = conectar()
    version = json.loads(Path(os.getenv('MODELO_PATH', '/models/sentimiento_v1'), 'lifemap_metadata.json').read_text())['version']
    negocio_id = 'ci_business'
    db.negocios.create_index([('location', '2dsphere')])
    db.negocios.replace_one({'_id': negocio_id}, {'_id': negocio_id,
        'location': {'type': 'Point', 'coordinates': [-82.45, 27.95]}, 'categoria_principal': 'Pizza',
        'primera_resena': fecha_utc('2017-01-01'), 'ultima_resena': fecha_utc('2019-05-01'),
        'fecha_corte': fecha_utc('2020-01-01'), 'evento': 0, 'is_open': 1}, upsert=True)
    db.resenas.replace_one({'_id': 'ci_historica'}, {'_id': 'ci_historica', 'business_id': negocio_id,
        'fecha': fecha_utc('2018-01-01'), 'estrellas': 3, 'etiqueta': 1}, upsert=True)
    prefijo = uuid.uuid4().hex
    ids = [f'{prefijo}-{i}' for i in range(100)]
    corte = fecha_utc(os.getenv('FECHA_CORTE', '2019-01-01'))
    productor = KafkaProducer(bootstrap_servers=os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092'),
        acks='all', key_serializer=lambda x: x.encode(), value_serializer=lambda x: json.dumps(x).encode())
    try:
        for _ in range(2):
            for i, rid in enumerate(ids):
                productor.send(topic, key='ci_business', value={'review_id': rid, 'business_id': 'ci_business',
                    'texto': 'Great food and friendly staff' if i % 2 else 'Terrible food and rude staff',
                    'date': (corte + timedelta(days=1, seconds=i)).isoformat(), 'estrellas': 5 if i % 2 else 1, 'geohash': 'dhvru7'}).get(timeout=30)
            productor.flush()
            consumer = KafkaConsumer(bootstrap_servers=os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092'), group_id=None)
            try:
                finales = consumer.end_offsets([TopicPartition(topic, i) for i in consumer.partitions_for_topic(topic)])
            finally:
                consumer.close()
            limite = time.monotonic() + args.timeout
            while time.monotonic() < limite:
                docs = list(db.reviews_live.find({'_id': {'$in': ids}}))
                progreso = (db.streaming_meta.find_one({'_id': 'progreso'}) or {}).get('offsets', {})
                completos = all(int(progreso.get(str(tp.partition), 0)) >= fin for tp, fin in finales.items())
                if completos and len(docs) == 100 and all(d.get('modelo_version') == version and len(d.get('probabilidades', [])) == 3 for d in docs):
                    break
                time.sleep(2)
            else:
                raise AssertionError('No llegaron 100 reseñas clasificadas con el modelo versionado.')
        score = db.risk_scores.find_one({'_id': negocio_id})
        if not score or not db.alerts.find_one({'_id': negocio_id}):
            raise AssertionError('El micro-lote no actualizó riesgo/alerta del negocio afectado.')
        # Avanza el watermark después del reenvío: comprueba deduplicación en la ventana.
        productor.send(topic, key=negocio_id, value={'review_id': prefijo + '-watermark', 'business_id': negocio_id,
            'texto': 'Great food', 'date': (corte + timedelta(days=120)).isoformat(),
            'estrellas': 5, 'geohash': 'dhvru7'}).get(timeout=30)
        productor.flush()
        limite = time.monotonic() + args.timeout
        while time.monotonic() < limite:
            ventana = db.live_windows.find_one({'geohash': 'dhvru7', 'n': 100})
            if ventana:
                break
            time.sleep(2)
        else:
            raise AssertionError('La ventana cerrada no contiene exactamente las 100 reseñas únicas.')
        print(json.dumps({'mensajes_unicos': 100, 'publicados': 201, 'mensajes_de_control': 1, 'modelo_version': version, 'estado': 'ok'}))
    finally:
        productor.close()
        client.close()


if __name__ == '__main__':
    main()
