"""Exporta evidencia e informe base desde ejecuciones reales; falla si falta evidencia E1."""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from pymongo import MongoClient
from pipeline_ingesta import _mongo_uri


def tabla(filas, columnas):
    encabezado = '| ' + ' | '.join(columnas) + ' |\n| ' + ' | '.join(['---'] * len(columnas)) + ' |'
    return encabezado + '\n' + '\n'.join('| ' + ' | '.join(str(f.get(c, '—')).replace('|', '/') for c in columnas) + ' |' for f in filas)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--salida', default='/data/evidencias')
    p.add_argument('--url', default=os.getenv('PUBLIC_URL', 'URL por registrar en README'))
    args = p.parse_args()
    client = MongoClient(_mongo_uri())
    db = client[os.getenv('MONGO_DB', 'lifemap')]
    try:
        ingesta = db.ingesta_meta.find_one({'estado': 'completa'}, sort=[('fin', -1)])
        sentimiento = db.modelo_metricas.find_one({'_id': 'sentimiento_v1'})
        tasas = db.tasas_meta.find_one({'_id': 'tasas'})
        balanceo = list(db.balanceo_resumen.find({}, {'_id': 0}))
        if not all([ingesta, sentimiento, tasas, balanceo]):
            raise SystemExit('Falta evidencia real de ingesta, sentimiento, tasas o balanceo. No se generó un informe con resultados inventados.')
        modelo = json.loads(sentimiento['json'])
        distribucion = list(db.balanceo_estadisticas.find({}, {'_id': 0}))
        top = list(db.tasas_categoria.find({'cumple_minimo': True}, {'_id': 0}).sort('tasa_cierre', -1).limit(10))
        riesgo = db.modelo_riesgo.find_one({'_id': 'riesgo_v1'})
        evidencia = {'exportado_en': datetime.now(timezone.utc).isoformat(), 'commit': os.getenv('GIT_COMMIT', 'no_informado'),
            'ingesta': ingesta, 'sentimiento': modelo, 'tasas': tasas, 'balanceo': balanceo,
            'distribucion_particiones': distribucion, 'riesgo': riesgo}
        base = Path(args.salida)
        base.mkdir(parents=True, exist_ok=True)
        (base / 'evidencia_ejecucion.json').write_text(json.dumps(evidencia, default=str, ensure_ascii=False, indent=2))
        reglas = []
        for tipo in ('negocios', 'resenas'):
            reporte = ingesta[tipo]
            antes = reporte['total_inicial']
            for regla, n in reporte.items():
                if regla.startswith(('N', 'R')) and isinstance(n, int):
                    reglas.append({'tipo': tipo, 'regla': regla, 'antes': antes, 'descartados': n, 'despues': antes-n})
                    antes -= n
        metricas = [{'modelo': nombre, 'accuracy': m['accuracy'], 'f1_macro': m['f1_macro'],
            'precision_clase': m['por_clase'], 'matriz': m['matriz_confusion']['valores']} for nombre, m in modelo['resultados'].items()]
        texto = f'''# LifeMap — informe técnico de la primera entrega

URL: {args.url}
Commit de ejecución: {evidencia['commit']}
Exportado: {evidencia['exportado_en']}

## 1. Arquitectura y reproducibilidad

Yelp/Kaggle → Dask (scheduler y dos workers) → MongoDB (GeoJSON y 2dsphere) → Spark
(sentimiento, MapReduce y balanceo) → Flask → túnel público. Jenkins construye imágenes,
ejecuta pytest e integración, prueba una API candidata y despliega. La descarga completa
queda automatizada; datos y modelos están en volúmenes y credenciales fuera de Git.
Área: {ingesta['area_estados']}; familia: {ingesta['familia']}.

## 2. Limpieza y construcción de la vida

Descartes secuenciales por regla, con antes y después:

{tabla(reglas, ['tipo','regla','antes','descartados','despues'])}

Negocios cargados: {ingesta['negocios']['total_final']}; reseñas cargadas:
{ingesta['resenas']['total_final']}; fecha de corte global: {ingesta['fecha_corte']}.
Se eliminan coordenadas inválidas, negocios fuera del área/categoría, reseñas sin texto,
fechas/estrellas inválidas y duplicados. La vida es de primera a última reseña, incluidos
ambos días. is_open=0 indica evento; is_open=1 indica censura. Apertura anterior a primera
reseña y cierre posterior a última reseña son limitaciones de la aproximación.

## 3. Sentimiento sin fuga

Tokenización y stopwords en inglés, TF-IDF y comparación Naive Bayes/regresión logística.
Separación por negocio; negocios cruzados: {modelo['negocios_cruzados']}.
Entrenamiento: {modelo['entrenamiento']}; prueba: {modelo['prueba']}.
Distribución de etiquetas: {modelo['distribucion_etiquetas']}. Ponderación inversa de
frecuencia en entrenamiento. Accuracy no basta cuando la clase positiva predomina.

{tabla(metricas, ['modelo','accuracy','f1_macro','precision_clase','matriz'])}

Modelo seleccionado: {modelo['modelo_activo']}; versión: {modelo['version']}.
Las métricas por clase permiten identificar falsos negativos/positivos y la matriz
muestra las confusiones; completar la interpretación específica al revisar estos resultados.

## 4. MapReduce y tasas

RDD emite (clave, (cierres, días-negocio)) y suma con reduceByKey por categoría y geohash.
Validación contra groupBy: {tasas['validacion_rdd_vs_groupby']}.
Tasa = cierres / (días-negocio / 365) × 100. Umbral de exposición:
{tasas['min_dias_negocio']} días-negocio; 18.250 equivale a 50 años-negocio y cada cierre
adicional mueve 2 puntos porcentuales. La tasa anualizada puede superar 100%; no es una
probabilidad. Se excluyen grupos por debajo del umbral de las comparaciones.

{tabla(top, ['categoria','negocios','cierres','dias_negocio','tasa_cierre'])}

## 5. Balanceo medido

{tabla(balanceo, ['particiones','media_s','desv_estandar_s'])}

{tabla(distribucion, ['reparto','min','max','media','particiones_vacias','max_sobre_media'])}

Comparar max/media y particiones vacías entre reparto sin clave, ciudad y categoría.
La concentración de claves puede dejar particiones vacías o sobrecargadas; el mejor
número de particiones se justifica con estos tiempos propios y la sobrecarga de scheduling.

## 6. Despliegue, evidencia y limitaciones

Los seis endpoints, validación y fórmula de tasa tienen pruebas. Adjuntar al informe final
los números/URLs del build verde, el build FORZAR_FALLO=true y el hash de /health. El código
por sí solo no demuestra disponibilidad durante 48 horas ni despliegue fuera del portátil.
El rollback de API no revierte datos/modelos compartidos. Citar Yelp Open Dataset y los
trabajos reutilizados de SentimentStream, geoespacial y discos; completar autores del equipo.

Este documento es una base con evidencia real, no una sustentación terminada. Revisar la
interpretación, autores y evidencias de Jenkins, y maquetar a máximo 6 páginas antes de entregar.
'''
        (base / 'informe_e1.md').write_text(texto, encoding='utf-8')
        print(f'Evidencia e informe base exportados a {base}')
    finally:
        client.close()


if __name__ == '__main__':
    main()
