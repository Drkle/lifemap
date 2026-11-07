"""Auditoría temporal de solo lectura sobre Yelp antes de entrenar o arrancar Kafka."""
import argparse
import json
from datetime import datetime, timezone
from collections import Counter
from analitica import fecha_utc, fin_horizonte, etiqueta_riesgo
from comun import conectar
from entrenar_riesgo import fold


def auditar(db, corte, entrenamiento):
    corte, entrenamiento = fecha_utc(corte), fecha_utc(entrenamiento)
    if fin_horizonte(entrenamiento) > corte:
        raise ValueError('El horizonte de etiquetas de entrenamiento debe terminar antes de T.')
    meta = db.negocios.find_one(sort=[('fecha_corte', -1)])
    if not meta or fecha_utc(meta['fecha_corte']) < fin_horizonte(corte):
        raise ValueError('El dataset debe observar al menos 12 meses después de T para evaluar riesgo.')
    antes = db.resenas.count_documents({'fecha': {'$lte': corte}})
    despues = db.resenas.count_documents({'fecha': {'$gt': corte}})
    if not antes or not despues:
        raise ValueError('Se requieren reseñas antes y después de T; no se cambian cortes automáticamente.')
    etiquetas = {str(r['_id']): r['n'] for r in db.resenas.aggregate([
        {'$match': {'fecha': {'$lte': corte}}}, {'$group': {'_id': '$etiqueta', 'n': {'$sum': 1}}}])}
    if set(etiquetas) != {'0', '1', '2'}:
        raise ValueError('El sentimiento anterior a T debe contener las tres clases.')
    cohortes = {k: Counter() for k in ('entrenamiento', 'validacion', 'prueba')}
    for n in db.negocios.find({}, {'primera_resena': 1, 'ultima_resena': 1, 'is_open': 1}):
        grupo = fold(n['_id'])
        t = corte if grupo >= 8 else entrenamiento
        if fecha_utc(n['primera_resena']) > t:
            continue
        y = etiqueta_riesgo(n, t)
        if y is not None:
            nombre = 'prueba' if grupo >= 8 else ('validacion' if grupo >= 6 else 'entrenamiento')
            cohortes[nombre][str(y)] += 1
    for nombre, conteos in cohortes.items():
        if not conteos.get('0') or not conteos.get('1'):
            raise ValueError(f'La cohorte {nombre} no tiene ambas clases: {dict(conteos)}. Revisar T con evidencia.')
    return {'auditado_en': datetime.now(timezone.utc).isoformat(), 'fecha_corte': corte.isoformat(),
        'corte_entrenamiento': entrenamiento.isoformat(), 'fecha_corte_dataset': fecha_utc(meta['fecha_corte']).isoformat(),
        'resenas_historicas': antes, 'resenas_reservadas_streaming': despues,
        'clases_sentimiento_historico': etiquetas, 'cohortes_riesgo': {k: dict(v) for k,v in cohortes.items()},
        'advertencias': [f'{k}: menos de 30 cierres; interpretar métricas con cautela' for k,v in cohortes.items() if v.get('1',0) < 30],
        'mutaciones_mongodb': False}


def main():
    import os
    p=argparse.ArgumentParser()
    p.add_argument('--corte', default=os.getenv('FECHA_CORTE','2019-01-01'))
    p.add_argument('--entrenamiento', default=os.getenv('CORTE_ENTRENAMIENTO','2018-01-01'))
    a=p.parse_args(); client,db=conectar()
    try:
        print(json.dumps(auditar(db,a.corte,a.entrenamiento),ensure_ascii=False,indent=2))
    finally:
        client.close()


if __name__=='__main__':
    main()
