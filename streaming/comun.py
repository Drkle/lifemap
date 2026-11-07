"""Conexiones y consultas de features: credenciales exclusivamente del entorno."""
import os
from urllib.parse import quote_plus
from pymongo import MongoClient


def conectar():
    user = quote_plus(os.getenv('MONGO_ROOT_USER', 'admin'))
    password = quote_plus(os.environ['MONGO_ROOT_PASSWORD'])
    host = os.getenv('MONGO_HOST', 'mongodb')
    client = MongoClient(f'mongodb://{user}:{password}@{host}:27017/?authSource=admin', serverSelectionTimeoutMS=5000)
    return client, client[os.getenv('MONGO_DB', 'lifemap')]


def competidores(db, negocio, corte):
    return next(db.negocios.aggregate([
        {'$geoNear': {'near': negocio['location'], 'key': 'location', 'distanceField': 'distancia', 'maxDistance': 500,
                     'spherical': True, 'query': {'categoria_principal': negocio['categoria_principal'],
                        'primera_resena': {'$lte': corte}, '_id': {'$ne': negocio['_id']}}}},
        {'$count': 'n'}]), {}).get('n', 0)


def historial(db, negocio_id, corte, incluir_live=False, inicio_live=None):
    # Un mismo review_id debe contribuir una sola vez, incluso si existe en histórico y live.
    filtro = {'business_id': negocio_id, 'fecha': {'$lte': corte}}
    if incluir_live and inicio_live:
        filtro['fecha']['$lte'] = min(corte, inicio_live)
    filas = {r['_id']: r for r in db.resenas.find(filtro, {'texto': 0})}
    if incluir_live:
        for r in db.reviews_live.find({'business_id': negocio_id, 'fecha': {'$lte': corte}}, {'texto': 0}):
            filas[r['_id']] = r
    return list(filas.values())
