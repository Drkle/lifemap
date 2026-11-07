"""Riesgo de cierre con evaluación temporal y negocios disjuntos; artefacto JSON portable."""
import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, recall_score, roc_auc_score, precision_recall_curve
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from analitica import FEATURES, etiqueta_riesgo, fecha_utc, fin_horizonte, variables
from comun import conectar, competidores, historial


def fold(business_id):
    return int(hashlib.sha256(business_id.encode()).hexdigest()[:8], 16) % 10


def cohorte(db, corte, prueba=False):
    filas, etiquetas, ids = [], [], []
    for negocio in db.negocios.find({'primera_resena': {'$lte': corte}}):
        if (fold(negocio['_id']) >= 8) != prueba:
            continue
        etiqueta = etiqueta_riesgo(negocio, corte)
        if etiqueta is None:
            continue
        historia = historial(db, negocio['_id'], corte)
        if not historia:
            continue
        v = variables(historia, corte, negocio['primera_resena'], competidores(db, negocio, corte))
        filas.append([v[f] for f in FEATURES])
        etiquetas.append(etiqueta)
        ids.append(negocio['_id'])
    if len(set(etiquetas)) < 2:
        raise ValueError(f'El corte {corte} no tiene dos clases; ajustar cortes con evidencia, no inventar métricas.')
    return np.asarray(filas), np.asarray(etiquetas), ids


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--corte', default=os.getenv('FECHA_CORTE', '2019-01-01'))
    p.add_argument('--entrenamiento', default=os.getenv('CORTE_ENTRENAMIENTO', '2018-01-01'))
    p.add_argument('--salida', default='/models/riesgo_v1.json')
    args = p.parse_args()
    corte, anterior = fecha_utc(args.corte), fecha_utc(args.entrenamiento)
    if fin_horizonte(anterior) > corte:
        p.error('La ventana de etiquetas de entrenamiento debe terminar antes del corte de prueba (>=365 días).')
    client, db = conectar()
    try:
        meta = db.negocios.find_one(sort=[('fecha_corte', -1)])
        if not meta or fecha_utc(meta['fecha_corte']) < fin_horizonte(corte):
            raise ValueError('Se requieren al menos 12 meses observados después del corte de prueba.')
        x, y, ids = cohorte(db, anterior)
        xt, yt, ids_test = cohorte(db, corte, prueba=True)
        if set(ids) & set(ids_test):
            raise AssertionError('Fuga de negocios')
        # La selección del umbral usa validación por negocio en el periodo de entrenamiento.
        mask = np.array([fold(i) < 6 for i in ids])
        if len(set(y[mask])) < 2 or len(set(y[~mask])) < 2:
            raise ValueError('No hay ambas clases en entrenamiento y validación; ampliar la cohorte.')
        pipeline = make_pipeline(StandardScaler(), LogisticRegression(class_weight='balanced', max_iter=1000, random_state=42))
        pipeline.fit(x[mask], y[mask])
        probs_val = pipeline.predict_proba(x[~mask])[:, 1]
        precision, recall, thresholds = precision_recall_curve(y[~mask], probs_val)
        f1 = 2 * precision[:-1] * recall[:-1] / np.maximum(precision[:-1] + recall[:-1], 1e-12)
        umbral = float(thresholds[np.argmax(f1)])
        probs = pipeline.predict_proba(xt)[:, 1]
        scaler, lr = pipeline.steps[0][1], pipeline.steps[1][1]
        modelo = {'version': datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S'),
            'features': list(FEATURES), 'media': scaler.mean_.tolist(), 'escala': scaler.scale_.tolist(),
            'coeficientes': lr.coef_[0].tolist(), 'intercepto': float(lr.intercept_[0]), 'umbral': umbral,
            'corte_entrenamiento': anterior.isoformat(), 'corte_evaluacion': corte.isoformat(),
            'seleccion_umbral': 'máximo F1 en validación por negocio del periodo anterior',
            'negocios_entrenamiento': int(mask.sum()), 'negocios_validacion': int((~mask).sum()), 'negocios_prueba': len(yt),
            'negocios_cruzados': 0, 'auc_roc': float(roc_auc_score(yt, probs)),
            'auc_pr': float(average_precision_score(yt, probs)), 'base_auc_pr': float(yt.mean()),
            'recall': float(recall_score(yt, probs >= umbral)),
            'limitacion': 'Estado final y última reseña aproximan el cierre; no se observan fechas reales. Estrellas y conteos se calculan desde reseñas hasta cada corte.'}
        destino = Path(args.salida)
        destino.parent.mkdir(parents=True, exist_ok=True)
        temporal = destino.with_suffix('.tmp')
        temporal.write_text(json.dumps(modelo, indent=2, ensure_ascii=False))
        temporal.replace(destino)
        db.modelo_riesgo.replace_one({'_id': 'riesgo_v1'}, {'_id': 'riesgo_v1', **modelo}, upsert=True)
        # Publica únicamente puntuaciones con features al corte de evaluación.
        for negocio in db.negocios.find({'primera_resena': {'$lte': corte}}):
            historia = historial(db, negocio['_id'], corte)
            if historia:
                from analitica import probabilidad
                v = variables(historia, corte, negocio['primera_resena'], competidores(db, negocio, corte))
                db.risk_scores.replace_one({'_id': negocio['_id']}, {'_id': negocio['_id'], 'location': negocio['location'],
                    'probabilidad': probabilidad(modelo, v), 'variables': v, 'fecha': corte, 'modelo_version': modelo['version']}, upsert=True)
        db.risk_scores.create_index([('location', '2dsphere')])
        print(json.dumps(modelo, ensure_ascii=False))
    finally:
        client.close()


if __name__ == '__main__':
    main()
