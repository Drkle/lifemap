"""Reproduce solo reseñas posteriores a T, en tiempo del evento, con confirmación Kafka."""
import argparse
import json
import os
import time
from datetime import datetime
from kafka import KafkaProducer
from analitica import fecha_utc
from comun import conectar


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--corte', default=os.getenv('FECHA_CORTE', '2019-01-01'))
    p.add_argument('--segundos-por-mes', type=float, default=10)
    p.add_argument('--limite', type=int, default=0)
    p.add_argument('--topic', default=os.getenv('KAFKA_TOPIC', 'reviews'))
    args = p.parse_args()
    if args.segundos_por_mes < 0 or args.limite < 0:
        p.error('La velocidad y el límite deben ser no negativos')
    client, db = conectar()
    producer = KafkaProducer(bootstrap_servers=os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092'),
        acks='all', retries=5, key_serializer=lambda x: x.encode(),
        value_serializer=lambda x: json.dumps(x).encode())
    try:
        cursor = db.resenas.find({'fecha': {'$gt': fecha_utc(args.corte)}}).sort([('fecha', 1), ('_id', 1)])
        if args.limite:
            cursor = cursor.limit(args.limite)
        primero, reloj, n = None, time.monotonic(), 0
        for r in cursor:
            fecha = fecha_utc(r['fecha'])
            primero = primero or fecha
            esperar = (fecha - primero).total_seconds() / (30 * 86400) * args.segundos_por_mes - (time.monotonic() - reloj)
            if esperar > 0:
                time.sleep(esperar)
            valor = {'review_id': r['_id'], 'business_id': r['business_id'], 'texto': r['texto'],
                     'date': fecha.isoformat(), 'estrellas': r['estrellas'], 'geohash': r['geohash']}
            producer.send(args.topic, key=r['business_id'], value=valor).get(timeout=30)
            n += 1
        producer.flush()
        print(json.dumps({'publicadas': n, 'corte': args.corte, 'topic': args.topic}))
    finally:
        producer.close()
        client.close()


if __name__ == '__main__':
    main()
