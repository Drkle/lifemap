"""Cálculos puros de supervivencia y riesgo, compartidos con los jobs de streaming."""
from __future__ import annotations

import math
from datetime import datetime, timedelta

FEATURES = ('sentimiento_medio', 'tendencia_negativa', 'estrellas', 'n_resenas', 'edad_dias', 'competidores_500m')


def fecha_utc(value):
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo is None else value.astimezone(__import__('datetime').timezone.utc).replace(tzinfo=None)
    return fecha_utc(datetime.fromisoformat(str(value).replace('Z', '+00:00')))


def variables(resenas, corte, primera, competidores=0):
    """Solo usa reseñas <= corte; estrellas de Yelp del snapshot nunca son una variable."""
    corte = fecha_utc(corte)
    filas = [r for r in resenas if fecha_utc(r['fecha']) <= corte]
    if not filas:
        raise ValueError('Sin historia anterior al corte')
    anteriores, recientes = [], []
    for r in filas:
        dias = (corte - fecha_utc(r['fecha'])).total_seconds() / 86400
        neg = int(r.get('prediccion', r.get('etiqueta', 2))) == 0
        if 0 <= dias < 90:
            recientes.append(neg)
        elif 90 <= dias < 180:
            anteriores.append(neg)
    media = lambda xs: sum(xs) / len(xs) if xs else 0.0
    return {
        'sentimiento_medio': media([int(r.get('prediccion', r.get('etiqueta', 2))) - 1 for r in filas]),
        'tendencia_negativa': media(recientes) - media(anteriores),
        'estrellas': media([float(r['estrellas']) for r in filas]),
        'n_resenas': len(filas),
        'edad_dias': max(1, (corte - fecha_utc(primera)).days + 1),
        'competidores_500m': int(competidores),
    }


def fin_horizonte(corte):
    corte = fecha_utc(corte)
    try:
        return corte.replace(year=corte.year + 1)
    except ValueError:  # 29 de febrero
        return corte.replace(year=corte.year + 1, day=28)


def etiqueta_riesgo(negocio, corte):
    """Proxy académico de cierre: excluye negocios sin actividad posterior a T."""
    corte = fecha_utc(corte)
    ultima = fecha_utc(negocio['ultima_resena'])
    if ultima <= corte:
        return None
    fin = fin_horizonte(corte)
    if not negocio['is_open'] and ultima <= fin:
        return 1
    if negocio['is_open'] or ultima > fin:
        return 0
    return None


def probabilidad(modelo, valores):
    x = [(float(valores[n]) - modelo['media'][i]) / modelo['escala'][i] for i, n in enumerate(modelo['features'])]
    z = modelo['intercepto'] + sum(a * b for a, b in zip(x, modelo['coeficientes']))
    return 1 / (1 + math.exp(-max(-700, min(700, z))))


def kaplan_meier(negocios, edad_previa_dias=0):
    """Origen: primera reseña, o edad previa estimada declarada; abiertos hasta corte.

    entry permite entrada tardía. La edad previa real no existe en Yelp y no se inventa.
    Las salidas son inclusivas en días, como dias_negocio de la Entrega 1.
    """
    filas = []
    for n in negocios:
        inicio = fecha_utc(n['primera_resena'])
        salida = fecha_utc(n['ultima_resena'] if n['evento'] else n['fecha_corte'])
        duracion = (salida - inicio).days + 1
        if duracion <= 0:
            raise ValueError('Fecha de salida anterior a primera reseña')
        filas.append((edad_previa_dias, edad_previa_dias + duracion, int(n['evento'])))
    if not filas:
        return {'n': 0, 'eventos': 0, 'mediana_dias': None, 'curva': []}
    curva = [{'dias': edad_previa_dias, 'supervivencia': 1.0, 'en_riesgo': len(filas), 'cierres': 0, 'censuras': 0}]
    s, mediana = 1.0, None
    for tiempo in sorted({f[1] for f in filas}):
        riesgo = sum(entry <= tiempo <= fin for entry, fin, _ in filas)
        eventos = sum(fin == tiempo and evento for _, fin, evento in filas)
        censuras = sum(fin == tiempo and not evento for _, fin, evento in filas)
        s *= 1 - eventos / riesgo
        if s <= .5 and mediana is None:
            mediana = tiempo
        curva.append({'dias': tiempo, 'supervivencia': s, 'en_riesgo': riesgo, 'cierres': eventos, 'censuras': censuras})
    return {'n': len(filas), 'eventos': sum(f[2] for f in filas), 'mediana_dias': mediana, 'curva': curva,
            'entrada_tardia_dias': edad_previa_dias,
            'limitacion': 'Yelp no registra apertura/cierre: edad previa es análisis de sensibilidad; con 0 se mide seguimiento desde la primera reseña.'}
