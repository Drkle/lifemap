"""Regresión con MongoDB real: escritura parcial, reintento y duplicados entre bloques.

Solo usa una base temporal ci_ingesta_<uuid> y la elimina al terminar.
"""
import uuid
import pandas as pd
from pymongo import MongoClient
from pipeline_ingesta import (_mongo_uri, agregar_resenas_persistidas, finalizar_reporte_resenas,
                              procesar_particion_resenas)
import limpieza


def comprobar():
    uri = _mongo_uri()
    nombre = 'ci_ingesta_' + uuid.uuid4().hex
    client = MongoClient(uri)
    db = client[nombre]
    info = {'a': {'geohash': 'dhvru7', 'categoria_principal': 'Pizza', 'ciudad': 'Tampa'},
            'b': {'geohash': 'dhvru7', 'categoria_principal': 'Pizza', 'ciudad': 'Tampa'}}
    filas = [
        {'review_id': 'r1', 'business_id': 'a', 'stars': 1, 'text': 'bad food', 'date': '2019-01-01'},
        {'review_id': 'r2', 'business_id': 'a', 'stars': 5, 'text': 'great food', 'date': '2019-01-03'},
        {'review_id': 'r3', 'business_id': 'b', 'stars': 3, 'text': 'ordinary food', 'date': '2019-01-05'},
    ]
    a, b = pd.DataFrame([filas[0], filas[0], filas[1]]), pd.DataFrame([filas[1], filas[2]])
    try:
        # Simula una tarea que alcanzó a guardar r1 y perdió su resultado antes del reintento.
        limpio, _ = limpieza.limpiar_resenas(pd.DataFrame([filas[0]]), info)
        db.resenas.insert_one(limpieza.documento_resena(limpio.to_dict('records')[0], info['a']))
        r_a = procesar_particion_resenas(a, info, uri, nombre, 'resenas', 1)
        r_a_reintento = procesar_particion_resenas(a, info, uri, nombre, 'resenas', 1)
        assert r_a == r_a_reintento, 'Repetir la tarea alteró los conteos devueltos'
        r_b = procesar_particion_resenas(b, info, uri, nombre, 'resenas', 1)
        assert r_b == procesar_particion_resenas(b, info, uri, nombre, 'resenas', 1)
        agregado, total = agregar_resenas_persistidas(db.resenas)
        reporte = finalizar_reporte_resenas([r_a_reintento, r_b], total)
        assert total == db.resenas.count_documents({}) == 3
        assert reporte['R5_duplicado'] == 2 and reporte['total_final'] == 3
        por_id = agregado.set_index('business_id').to_dict('index')
        assert por_id['a']['n'] == 2 and por_id['a']['negativas'] == 1 and por_id['a']['suma_puntaje'] == 0
        assert por_id['b']['n'] == 1
        assert por_id['a']['primera'] == pd.Timestamp('2019-01-01')
        assert por_id['a']['ultima'] == pd.Timestamp('2019-01-03')
        print('[regresión MongoDB] OK: escritura parcial + reintentos + duplicados; 3 reseñas únicas, agregados completos.')
    finally:
        assert nombre.startswith('ci_ingesta_')
        client.drop_database(nombre)
        client.close()


if __name__ == '__main__':
    comprobar()
