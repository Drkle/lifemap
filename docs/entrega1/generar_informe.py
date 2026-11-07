"""Genera el informe HTML de seis páginas con evidencia de los builds #8 y #10; solo stdlib.

El PDF se obtiene con Imprimir > Guardar como PDF (A4, escala 100 %, sin encabezados del navegador).
No consulta MongoDB ni necesita credenciales. Requiere los JSON revisados de docs/evidencias.
"""
from pathlib import Path
from html import escape as h
import json

ROOT = Path(__file__).resolve().parents[2]
d = json.loads((ROOT/'docs/evidencias/build8_resultados.json').read_text())
api = json.loads((ROOT/'docs/evidencias/api_publica_build8.json').read_text())
ing = d['ingesta']; modelos = d['sentimiento']['resultados']


def n(x):
    return f'{x:,}'.replace(',', '.')


def tabla(headers, rows, clase=''):
    return '<table class="'+clase+'"><thead><tr>'+''.join('<th>'+h(str(x))+'</th>' for x in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+h(str(x))+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table>'


def pagina(numero, titulo, contenido):
    return f'<section class="pagina"><div class="ceja">BIG DATA · IUE · 2026-2 · ENTREGA 1</div><h1>{titulo}</h1>{contenido}<footer>LifeMap · Juan Echeverrri · Sebastian Botero <span>{numero} / 6</span></footer></section>'


def matrix(nombre):
    return tabla(['Real / Predicha', 'Negativo', 'Neutral', 'Positivo'], [[clase]+[n(v) for v in fila] for clase,fila in zip(['Negativo','Neutral','Positivo'],modelos[nombre]['matriz_confusion'])])

estados=tabla(['Componente', 'Evidencia observada'], [
    ['Jenkins', 'Build #8: SUCCESS; build #10: fallo intencional y bloqueo aprobado'],
    ['Commit del análisis', d['commit']], ['MongoDB / Spark / Dask', 'Estado ok; 1 worker Spark y 2 workers Dask'],
    ['Datos', '8.731 negocios y 792.133 reseñas; descarga completa automatizada'],
    ['Sentimiento', 'Regresión logística guardada; /predict aprobado'],
    ['Máquina de presentación', 'El mismo portátil de desarrollo, por decisión del equipo']])
arquitectura='''<svg viewBox="0 0 680 150" aria-label="Arquitectura batch"><defs><marker id="flecha" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0L8 4L0 8" fill="#13756f"/></marker></defs><g fill="#edf5f4" stroke="#13756f"><rect x="5" y="15" width="135" height="70" rx="8"/><rect x="180" y="15" width="135" height="70" rx="8"/><rect x="355" y="15" width="135" height="70" rx="8"/><rect x="530" y="15" width="145" height="70" rx="8"/></g><g font-family="Arial" font-size="13" text-anchor="middle" fill="#153a42"><text x="72" y="43">Kaggle / Yelp</text><text x="72" y="64">Dask · limpieza</text><text x="247" y="43">MongoDB</text><text x="247" y="64">GeoJSON · índices</text><text x="422" y="43">Spark</text><text x="422" y="64">ML · RDD · tasas</text><text x="602" y="43">Flask + ngrok</text><text x="602" y="64">API pública</text><text x="340" y="125">Jenkins + GitHub: build → pruebas → staging → despliegue</text></g><g stroke="#13756f" stroke-width="2" marker-end="url(#flecha)"><path d="M140 50H175"/><path d="M315 50H350"/><path d="M490 50H525"/></g></svg>'''
p1=pagina(1,'LifeMap: reputación, ubicación<br>y supervivencia de negocios',f'''
<p class="autores"><b>Juan Echeverrri · Sebastian Botero</b><br>Institución Universitaria de Envigado · Ingeniería · 7 de noviembre de 2026</p>
<h2>Propósito y alcance</h2><p>Integrar ubicación, reputación textual y exposición temporal para consultar negocios y comparar tasas de cierre en el área de Yelp identificada por Florida (FL), familia <b>Restaurants</b>. El recorte usa el estado; no se aplicó una caja geográfica adicional. La vida se aproxima por las fechas de reseñas, pues Yelp no contiene apertura ni cierre reales.</p>
<h2>Arquitectura y operación</h2>{arquitectura}<p>Un Compose orquesta MongoDB, Spark maestro/worker, Dask scheduler/dos workers, Flask y Jenkins. La ingesta descarga y limpia; Spark entrena y agrega; Flask consulta MongoDB y carga el modelo compartido para inferencia. GitHub dispara Jenkins por webhook, con polling cada dos minutos como respaldo. Código en imágenes; datos y modelos en volúmenes; credenciales fuera de Git.</p>
<h2>Resultado de la ejecución</h2>{estados}
<p><b>Repositorio:</b> <a href="https://github.com/Drkle/lifemap">github.com/Drkle/lifemap</a><br><b>API:</b> <a href="{api['base_url']}/health">{api['base_url']}/health</a><br><b>Dashboard:</b> <a href="{api['base_url']}/dashboard">/dashboard</a></p>
<p class="nota">El build y la comprobación pública son evidencia de funcionamiento en ese instante. No acreditan 48 horas de disponibilidad ni sustituyen el requisito de un servidor separado del portátil.</p>
''')
reglas=[]
for nombre,tipo in [('negocios','Negocios'),('resenas','Reseñas')]:
    rep=ing[nombre];antes=rep['total_inicial']
    for k,v in rep.items():
        if k.startswith(('N','R')) and isinstance(v,int):
            reglas.append([tipo,k,n(antes),n(v),n(antes-v)]);antes-=v
etiquetas=ing['resenas']['por_etiqueta_antes_R5']
p2=pagina(2,'Datos, limpieza y vida observada',f'''
<p>La descarga de <code>yelp-dataset/yelp-dataset</code> incluyó business.json (118.863.795 bytes) y review.json (5.341.868.833 bytes). Dask leyó <b>150.346 negocios y 6.990.280 reseñas</b>; procesó las 333 particiones de reseñas. Se conservaron todas las reseñas válidas del área/familia, no una muestra limitada a las primeras particiones. Tiempo de ingesta: <b>590,8 s</b>.</p>
<h2>Descartes secuenciales</h2>{tabla(['Tipo','Regla','Antes','Descartadas','Después'],reglas,'limpieza')}
<p>Se excluyen coordenadas inválidas, negocios fuera del recorte o sin la familia elegida, estado abierto/cerrado inválido y reseñas sin texto, estrellas/fechas válidas o identificador único. Las cifras cero indican reglas ejecutadas sin descartes en esta ejecución. Cada reseña referencia su negocio; cada negocio guarda un Point GeoJSON en orden longitud–latitud con índice <code>2dsphere</code>.</p>
<h2>Reintentos y consistencia</h2><p>Los bloques escriben por <code>review_id</code> con upsert idempotente. Repetir una tarea no descuenta documentos ya guardados. Los agregados de vida se calculan desde las reseñas únicas de MongoDB y se validan los conteos. Para controlar memoria se usan dos tareas activas, bloques de 16 MB y un hilo por worker; los argumentos del grafo se pueden reconstruir tras una caída.</p>
<p><b>Vida:</b> primera a última reseña, contando ambos días. Se observaron {n(ing['vida']['cierres_observados'])} cierres y {n(ing['vida']['censurados'])} negocios censurados, con {n(ing['vida']['dias_negocio_total'])} días-negocio; mediana de seguimiento de 2.115 días. Corte global del dataset: <b>19/01/2022, 19:48:45</b>.</p>
<p class="nota">Aperturas anteriores a la primera reseña generan entrada tardía no observada. Un abierto no se trata como cierre. En esta entrega, la exposición de la tasa usa primera–última reseña; se almacena además el seguimiento hasta el corte para estudiar censura en la segunda entrega.</p>
''')
filasmetricas=[]
for nombre,rotulo in [('naive_bayes','Naive Bayes'),('regresion_logistica','Regresión logística')]:
    for clase,m in modelos[nombre]['por_clase'].items():
        filasmetricas.append([rotulo,clase,f"{m['precision']:.3f}",f"{m['recall']:.3f}",f"{m['f1']:.3f}",n(m['soporte'])])
p3=pagina(3,'Sentimiento: comparación sin fuga',f'''
<p>Etiqueta: 1–2 estrellas = negativo; 3 = neutral; 4–5 = positivo. En las 792.133 reseñas: <b>{etiquetas['positivo']/792133*100:.2f} % positivas, {etiquetas['negativo']/792133*100:.2f} % negativas y {etiquetas['neutral']/792133*100:.2f} % neutrales</b>. Se conserva el patrón de SentimentStream: tokenización y stopwords en inglés, HashingTF/IDF y clasificadores MLlib.</p>
<p>El muestreo aleatorio de entrenamiento conservó 300.361 reseñas (objetivo aproximado: 300.000). La separación se hizo por hash de <code>business_id</code>: 244.621 filas para entrenar y 55.740 para prueba, con <b>cero negocios compartidos</b>. IDF se ajustó solo en entrenamiento. Las clases se ponderaron por frecuencia inversa.</p>
{tabla(['Modelo','Accuracy','F1 macro'],[['Naive Bayes','0,7898','0,6746'],['Regresión logística','0,8215','0,7008']])}
<h2>Resultados por clase</h2>{tabla(['Modelo','Clase','Precisión','Recall','F1','Soporte'],filasmetricas)}
<div class="dos"><div><h3>Matriz: Naive Bayes</h3>{matrix('naive_bayes')}</div><div><h3>Matriz: regresión logística</h3>{matrix('regresion_logistica')}</div></div>
<p class="nota">Matrices: filas = etiqueta real; columnas = predicción. Orden: negativo, neutral, positivo. Métricas por clase calculadas desde los conteos de confusión de la consola; redondeo a tres decimales.</p>
<h2>Interpretación y modelo activo</h2><p>Se eligió <b>regresión logística</b> por su mayor F1 macro (+0,0262). Mejora F1 negativo a 0,783 y positivo a 0,912. Neutral sigue siendo la clase más difícil: precisión 0,340 y recall 0,509; de 5.679 neutrales reales, 2.890 se clasificaron correctamente, 1.431 como negativos y 1.358 como positivos. La precisión neutral baja evidencia falsos positivos y limita la interpretación de reseñas ambiguas.</p>
<p>La mayoría positiva hace insuficiente reportar solo accuracy. F1 macro pondera igual las tres clases, pero no reemplaza sus métricas individuales. El modelo se guardó en <code>/models/sentimiento_v1</code>, versión <code>20261107052058</code>; la API lo cargó y superó la prueba de predicción.</p>
''')
top=api['consultas']['closure']['respuesta']['resultados'][:6]
filastasas=[[r['categoria'],n(r['negocios']),n(r['cierres']),f"{r['anios_negocio']:.2f}",f"{r['tasa_cierre']:.3f}"] for r in top]
p4=pagina(4,'MapReduce, tasas y consultas espaciales',f'''
<h2>Exposición y fórmula</h2><p>RDD emite <code>(clave, (evento, días_negocio, 1))</code> y suma con <code>reduceByKey</code> por categoría principal y geohash. Los resultados se contrastaron con <code>groupBy</code> de DataFrames; la prueba de la semilla validó valores conocidos antes de calcular los datos reales. El porcentaje de reseñas negativas por celda se agrega también por clave.</p>
<div class="formula">Tasa anualizada (%) = cierres ÷ (días-negocio ÷ 365) × 100</div>
<p>Resultado global: <b>2.811 cierres / (19.734.885 / 365) × 100 = 5,199</b> cierres por 100 años-negocio. La proporción de negocios cerrados es {2811/8731*100:.2f} %, pero esa proporción no es una tasa anualizada. Una tasa de exposición tampoco es la probabilidad individual de cierre en un año.</p>
<p>Para comparar grupos se exigen <b>18.250 días-negocio</b> (50 años-negocio). En ese umbral un cierre adicional mueve la tasa dos puntos porcentuales; reduce la sensibilidad extrema de grupos de exposición mínima, pero no elimina la incertidumbre por pocos eventos. El umbral es un parámetro de la API.</p>
<h2>Categorías con mayor tasa entre grupos elegibles</h2>{tabla(['Categoría','Negocios','Cierres','Años-negocio','Tasa (%)'],filastasas)}
<p class="nota">Fuente: /stats/closure en la comprobación pública. No interpretar el ranking como causalidad: categoría, ubicación y patrón de reseñas pueden afectar tanto la exposición medida como la selección de negocios.</p>
<h2>Modelo geoespacial y operaciones</h2>{tabla(['Endpoint','Operación y resultado'],[
['GET /businesses/near','$near: negocios por distancia; lat, lon, radio y categoría opcional'],
['POST /businesses/within','$geoWithin: negocios dentro de un Polygon GeoJSON'],
['GET /zones/summary','$geoNear + agregación: sentimiento medio y tasa cerca de un punto'],
['GET /stats/closure','Tasas precalculadas por categoría o celda, con mínimo de exposición'],
['POST /predict','Sentimiento de texto nuevo con el PipelineModel guardado'],
['GET /health','Estado de servicios, modelo, versión y commit desplegado']])}
<p>La API valida coordenadas, radios, límites, polígonos y texto. Geohash de precisión 6 aporta celdas de aproximadamente 1,2 × 0,6 km según latitud. El dashboard web consulta automáticamente la API cada 15 segundos; las vistas de streaming permanecen vacías hasta ejecutar la segunda entrega.</p>
''')
mediciones={p:[r['segundos'] for r in d['balanceo_repeticiones'] if r['particiones']==p] for p in [2,8,32,200]}
filastiempos=[]
for r in d['balanceo_resumen']:
    filastiempos.append([r['particiones']]+[f'{x:.3f}' for x in mediciones[r['particiones']]]+[f"{r['media_s']:.3f}",f"{r['desv_estandar_s']:.3f}"])
p5=pagina(5,'Balanceo de carga: mediciones propias',f'''
<p>Experimento sobre <b>792.133 reseñas</b>, Spark 3.5.3 y un worker con dos cores. Se cronometró la operación de agregación con 2, 8, 32 y 200 particiones, tres repeticiones por configuración. La tabla conserva los valores medidos del build #8, no resultados de una simulación.</p>
<h2>Tiempos en segundos</h2>{tabla(['Particiones','Repetición 1','Repetición 2','Repetición 3','Media','Desv. estándar'],filastiempos)}
<h2>Filas por partición: 32 particiones</h2>{tabla(['Reparto','Mínimo','Máximo','Media','Vacías','Máx./media'],[[r['reparto'],n(r['min']),n(r['max']),f"{r['media']:.1f}",r['vacias'],r['max_media']] for r in d['distribucion_particiones']])}
<h2>Interpretación</h2><p>El reparto sin clave es casi uniforme: 24.752–24.756 filas por partición y relación máximo/media de 1,0. Por ciudad, una partición concentra 305.069 filas (12,32 veces la media) y otra queda vacía. Por categoría, el máximo llega a 106.082 (4,29 veces la media). Estos conteos sustentan el sesgo; no se infiere únicamente de los tiempos.</p>
<p>En este hardware, dos particiones dieron la menor media (2,038 s), seguidas de ocho (2,264 s). La primera repetición de dos fue 2,864 s frente a 1,592 y 1,657 s después: hay variabilidad y posible calentamiento. No se separó una fase de warm-up, por lo que una diferencia pequeña entre 2 y 8 no demuestra superioridad universal.</p>
<p>Con 200 particiones la media subió a 32,084 s, unas 15,7 veces el valor de dos. El mayor paralelismo potencial no se aprovecha en un worker de dos cores y añade planificación, serialización e intercambio. La recomendación se limita a esta carga y configuración; debe repetirse si cambia el tamaño del dataset o el clúster.</p>
<h2>Reproducibilidad</h2><p><code>spark/jobs/balanceo.py</code> guarda tiempos individuales, medias, dispersión y distribución en MongoDB y exporta CSV a <code>/data/evidencias</code>. Los JSON revisados del repositorio incluyen las 12 repeticiones; el hash del texto aportado permite rastrear la fuente de los números.</p>
<p class="nota">No se alteraron los datos para obtener un reparto favorable. La comparación con/sin clave conserva el sesgo real de ciudad y categoría.</p>
''')
validaciones=[[v['metodo']+' '+v['ruta'].split('?')[0],v['http'],f"{v['segundos']:.3f} s"] for v in api['consultas'].values()]
p6=pagina(6,'Despliegue, validación y pendientes',f'''
<h2>Ejecución CI/CD</h2><p>El build #8 fue iniciado por un cambio SCM y terminó en <b>SUCCESS</b>. Cubrió construcción, pruebas API/ingesta/Spark, Kaggle, servicios, ingesta, integración, semilla determinista, cálculo real, staging y despliegue. La API candidata y la desplegada aprobaron /health y /predict. Kafka se omitió con <code>ENTREGA2=false</code>.</p>
<h2>Comprobación de la URL pública</h2><p>Fecha: <b>{h(api['verificado_en'])}</b> (America/Bogota). Los tiempos son observaciones de red de una sola consulta; no un benchmark de latencia.</p>{tabla(['Método / ruta','HTTP','Tiempo observado'],validaciones)}
<p>La respuesta de /health informó commit <code>{d['commit']}</code>, versión 8, MongoDB/Spark/Dask/API en estado ok y modelo disponible. La consulta geográfica devolvió negocios reales de Tampa; tasas y predicción respondieron con datos del modelo entrenado.</p>
<h2>Fallo controlado y alcance de presentación</h2><ol><li><b>Bloqueo confirmado, build #10:</b> FORZAR_FALLO=true hizo fallar test_fallo_intencional. Las etapas posteriores, incluido despliegue, quedaron omitidas. El script confirmó [bloqueo] OK y Jenkins archivó la evidencia. La comprobación pública posterior mostró versión 9 y commit 56a7031, con la imagen lifemap-api:9 conservada.</li><li><b>Máquina elegida:</b> el equipo decidió desarrollar y presentar en este mismo portátil, sin traslado. Se documenta la diferencia respecto a la condición de otra máquina de la sección 6; no se declara cumplida esa condición.</li><li><b>Disponibilidad:</b> falta acreditar la ventana de 48 horas hasta la sustentación. Las consultas puntuales no prueban continuidad.</li></ol>
<h2>Limitaciones y continuación</h2><p>Yelp no observa fechas reales de apertura/cierre; primera/última reseña son proxies y la entrada tardía no se conoce. La tasa de la primera entrega usa exposición por reseñas, mientras Kaplan-Meier deberá extender abiertos hasta el corte y tratar censura. El rollback restaura la imagen de API, no las mutaciones de datos/modelos compartidos; las recargas requieren mantenimiento. El modelo de sentimiento no reserva todavía datos posteriores a T en esta ejecución: se reentrenará con corte explícito antes del streaming.</p>
<h2>Fuentes y trazabilidad</h2><p class="fuentes">[1] Enunciado «LifeMap: reputación, ubicación y supervivencia de negocios», Big Data IUE 2026-2, secciones 4–7.<br>[2] Yelp Open Dataset, Yelp Inc., distribuido en Kaggle: <a href="https://www.kaggle.com/datasets/yelp-dataset/yelp-dataset">yelp-dataset/yelp-dataset</a>; uso académico sujeto a sus términos.<br>[3] Repositorio <a href="https://github.com/Drkle/lifemap">Drkle/lifemap</a>, commit b5f6745; PR #5 y #6. Patrones del curso: SentimentStream (texto), trabajo geoespacial (Compose/API) y ejercicio de discos (MapReduce/tasa).<br>[4] Consola Jenkins lifemap-main #8 aportada por el equipo; datos extraídos en docs/evidencias/build8_resultados.json y comprobación externa en api_publica_build8.json; consola y health posteriores al fallo controlado en bloqueo_build10.json.</p>
''')
css='''@page{size:A4;margin:15mm}*{box-sizing:border-box}body{margin:0;color:#162f3a;font-family:Arial,sans-serif;font-size:9pt;line-height:1.28}.pagina{width:180mm;height:266mm;position:relative;break-after:page;padding-bottom:13mm;overflow:hidden}.pagina:last-child{break-after:auto}.ceja{font-size:7.5pt;font-weight:bold;letter-spacing:1px;color:#13756f;border-bottom:2px solid #13756f;padding-bottom:5px}h1{font-size:20pt;line-height:1.12;margin:16px 0 12px}h2{font-size:12pt;color:#13756f;margin:14px 0 6px}h3{font-size:9pt;margin:10px 0 5px}p{margin:7px 0}table{width:100%;border-collapse:collapse;font-size:8pt;line-height:1.22;margin:7px 0;table-layout:auto}th{text-align:left;background:#eaf2f3;color:#163b42}th,td{padding:5px 6px;border:1px solid #cfdde1;vertical-align:top}td code,code{overflow-wrap:anywhere;font-size:8pt}tr:nth-child(even)td{background:#f7fafb}.limpieza{font-size:7.8pt}.limpieza td,.limpieza th{padding:4px}footer{position:absolute;bottom:0;left:0;right:0;border-top:1px solid #cfdde1;padding-top:6px;font-size:7.5pt;color:#536a76}footer span{float:right}.autores{font-size:10pt;color:#425b65}.nota,.fuentes{font-size:8pt;color:#425b65}.dos{display:flex;gap:10px}.dos>div{width:50%}.dos table{font-size:7.8pt}.formula{background:#eaf2f3;padding:13px;text-align:center;font-size:12pt;font-weight:bold;margin:10px 0}svg{width:100%;max-height:145px}a{color:#0c655f;overflow-wrap:anywhere}ol{padding-left:18px}li{margin:6px 0}@media screen{body{background:#e7edef;padding:20px}.pagina{background:white;margin:0 auto 20px;padding:15mm;width:210mm;height:297mm;box-shadow:0 3px 20px #0001}.pagina footer{left:15mm;right:15mm;bottom:15mm}}'''
html='<!doctype html><html lang="es"><head><meta charset="utf-8"><title>LifeMap · Informe Entrega 1 · Builds 8 y 10</title><style>'+css+'</style></head><body>'+p1+p2+p3+p4+p5+p6+'</body></html>'
(ROOT/'docs/entrega1/informe_e1.html').write_text(html,encoding='utf-8')
print('Informe HTML de seis páginas generado.')
