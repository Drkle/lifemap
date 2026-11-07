"""Informe de avance: fuentes versionadas y consultas reales, sin resultados simulados."""
import json
from html import escape
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
load=lambda p:json.loads((ROOT/p).read_text())
e1=load('docs/evidencias/build8_resultados.json')
e2=load('docs/evidencias/preparacion_build13.json')
z=load('docs/evidencias/supervivencia_zonas_20261107.json')['resultados']

def tabla(head,rows):
    return '<table><thead><tr>'+''.join('<th>'+escape(str(c))+'</th>' for c in head)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+escape(str(c))+'</td>' for c in row)+'</tr>' for row in rows)+'</tbody></table>'

def p(s):return '<p>'+s+'</p>'
def h(s):return '<h2>'+s+'</h2>'
pages=[]
def pagina(title,body):
    pages.append('<section><div class="ceja">BIG DATA · LIFEMAP · INFORME DE AVANCE · 7 NOV 2026</div><h1>'+title+'</h1>'+body+'<footer>LifeMap · Santiago Villamizar Mejía · Juan Echeverri · Sebastián Botero <span>'+str(len(pages)+1)+' / 7</span></footer></section>')

pagina('LifeMap: reputación, ubicación y supervivencia de negocios',
 p('<b>Santiago Villamizar Mejía · Juan Echeverri · Sebastián Botero</b><br>Institución Universitaria de Envigado · 2026-2')+
 h('Resumen')+p('LifeMap integra procesamiento distribuido, consultas geoespaciales, análisis de texto y streaming para estudiar negocios de restaurantes en Florida a partir de Yelp. La plataforma seleccionó 8.731 negocios y 792.133 reseñas. La ampliación temporal procesó una muestra real de 20.000 reseñas únicas, calculó riesgo para 3.972 negocios y persistió 1.738 ventanas cerradas. Power BI Desktop cargó y representó mapa, alertas, supervivencia y evolución de sentimiento.')+
 h('Objetivo')+p('Relacionar reputación, ubicación y seguimiento temporal mediante una plataforma reproducible. Se busca detectar variaciones negativas por zona y explorar asociaciones con un indicador de cierre, sin confundir predicción, causalidad y observación real.')+
 h('Alcance de este documento')+p('<b>Borrador de avance para revisión del profesor.</b> Resume resultados observados, decisiones y limitaciones. No declara terminados los requisitos de actualización automática de Power BI, disponibilidad de 48 horas ni sustentación. La ejecución permanece en el portátil del equipo; ello difiere del requisito de un servidor distinto al portátil de desarrollo.')+
 p('Repositorio: <a href="https://github.com/Drkle/lifemap">github.com/Drkle/lifemap</a><br>API demostrada: <a href="https://aviation-decrease-hunger.ngrok-free.dev">aviation-decrease-hunger.ngrok-free.dev</a>. La URL depende del túnel y del portátil encendido.'))

pagina('Arquitectura y preparación de los datos',
 tabla(['Componente','Responsabilidad'],[['Dask: scheduler y dos workers','Lectura particionada, filtrado y carga idempotente'],['MongoDB','Negocios y reseñas; índices 2dsphere; resultados y alertas'],['Spark: maestro y worker','Sentimiento, tasas de cierre y experimentos de particionado'],['Kafka KRaft + Structured Streaming','Tres particiones; business_id como clave; inferencia y ventanas'],['Flask + Jenkins','Consultas geoespaciales, salud, pruebas y despliegue'],['Power BI Desktop','Modelo Import conectado a la API y cuatro visuales']])+
 h('Flujo de información')+p('Yelp → Dask → MongoDB → Spark/modelos; reseñas posteriores al corte → productor Kafka → Structured Streaming → MongoDB → Flask → Power BI. Docker Compose coordina servicios. Los modelos y checkpoints usan volúmenes persistentes y revisión de versiones.')+
 h('Selección y limpieza')+p('La lectura completa recorrió 150.346 negocios y 6.990.280 reseñas. Se conservaron restaurantes de Florida con ubicación válida y reseñas asociadas; quedaron 8.731 negocios y 792.133 reseñas. Se verificaron coordenadas, área, categoría, estado, estrellas, fechas y texto. La evidencia detallada antes/después de cada regla se conserva en el informe de la entrega 1 y build8_resultados.json.')+
 p('Las escrituras por identificador y el recuento desde los documentos persistidos evitan inflar los totales en reintentos de Dask. El procesamiento se acotó a dos tareas en vuelo y bloques de 16 MB para adaptarse a la memoria del portátil.'))

pagina('Cortes temporales y modelos',
 p('Se fijó T = 1 de enero de 2019. La auditoría separó 510.850 reseñas históricas y reservó 281.283 para reproducción posterior. El entrenamiento de riesgo usa un corte anterior: 1 de enero de 2018. La selección de variables respeta cada corte; la separación por negocio evita que el mismo identificador aparezca en entrenamiento y prueba.')+
 h('Sentimiento congelado')+p('La regresión logística temporal obtuvo accuracy 0,8093 y F1 macro 0,6988. El consumidor carga la versión 20261107061724 y no la reentrena durante la reproducción. Los candidatos temporales se guardan separados del modelo histórico de la entrega 1; usar el histórico completo para reseñas de 2019 produciría fuga temporal.')+
 h('Riesgo de cierre')+p('Variables: sentimiento medio, tendencia negativa de seis meses, estrellas, cantidad de reseñas, edad desde la primera reseña y competidores de la misma categoría a 500 m. Se excluyen negocios sin actividad posterior al corte. La etiqueta positiva aproxima cierre en los siguientes doce meses mediante estado final y última reseña.')+
 tabla(['Indicador','Resultado'],[['Entrenamiento / validación / prueba','3.320 / 1.051 / 1.073 negocios'],['Negocios cruzados entre conjuntos','0'],['AUC-ROC','0,5763'],['AUC-PR / prevalencia de referencia','0,0942 / 0,0792'],['Recall / umbral','0,3176 / 0,5656']])+
 p('El umbral maximiza F1 en validación del periodo anterior. El resultado tiene capacidad discriminativa limitada: supera poco la referencia de prevalencia. Las alertas son una herramienta exploratoria; no justifican decisiones automáticas sobre negocios.'))

pagina('Streaming y evidencia de operación',
 h('Tiempo del evento')+p('El productor consulta reseñas posteriores a T, ordenadas por fecha e identificador, y admite límite y velocidad configurable. Kafka conserva la clave business_id. El consumidor aplica el modelo de sentimiento congelado y escribe por review_id para controlar duplicados. Un segundo flujo agrega ventanas de 30 días por geohash con watermark de 7 días; las ventanas se publican cuando cierran.')+
 h('Definición de hotspot')+p('Se marca una celda cuando el porcentaje de negativas aumenta al menos 15 puntos porcentuales respecto a la ventana anterior y ambas ventanas tienen al menos 20 reseñas. El mínimo reduce cambios extremos con volúmenes pequeños y el salto prioriza deterioros notorios. Son valores operativos iniciales: falta un análisis de sensibilidad que mida su estabilidad; no equivalen a significancia estadística.')+
 tabla(['Prueba observada','Resultado'],[['Jenkins #13: preparación temporal','SUCCESS; candidatos y prueba de 100 reseñas'],['Jenkins #14: versión inválida intencional','FAILURE esperado; despliegue bloqueado'],['Jenkins #19: activación de E2','SUCCESS; Kafka y cuatro endpoints aprobados'],['Reproducción real','20.000 reseñas únicas guardadas'],['Puntuaciones / ventanas cerradas','3.972 negocios / 1.738 ventanas'],['Salud al finalizar','Consumidor activo; tres particiones; lag 0']])+
 p('Se enviaron primero 1.000 reseñas y después las primeras 20.000 desde el mismo corte. El total persistido de 20.000 confirma que el reenvío no aumentó el número de documentos únicos en esta prueba. Hubo lotes más lentos que el intervalo de 5 segundos; posteriormente el consumidor alcanzó los offsets finales. Los resultados proceden de las consolas aportadas por el equipo, no de datos sintéticos.'))

rows=[]
colors=['#13756f','#2457a7','#cd5d37']
paths=[]
for (nombre,item),color in zip(z.items(),colors):
 r=item['resultado'];rows.append([nombre,r['n'],r['eventos'],r['mediana_dias'] if r['mediana_dias'] is not None else 'No alcanzada'])
 pts=r['curva'];coords=[]
 for point in pts:
  x=45+500*min(point['dias'],7000)/7000;y=205-180*point['supervivencia'];coords.append(f'{x:.1f},{y:.1f}')
 paths.append(f'<polyline points="{" ".join(coords)}" fill="none" stroke="{color}" stroke-width="2"/>')
chart='<svg viewBox="0 0 580 235" role="img" aria-label="Curvas Kaplan Meier calculadas desde la API"><path d="M45 20V205H550" fill="none" stroke="#667"/><text x="5" y="25">100%</text><text x="15" y="205">0%</text><text x="45" y="225">0 días</text><text x="495" y="225">7000 días</text>'+''.join(paths)+'</svg>'
pagina('Supervivencia por categoría y zona',
 p('Se consultó /survival/Pizza y se repitió con dos polígonos mediante POST. Las cajas delimitan zonas de análisis y no son fronteras administrativas oficiales. Los vértices exactos, las curvas y el número en riesgo en cada tiempo se conservan en supervivencia_zonas_20261107.json.')+
 tabla(['Cohorte Pizza','Negocios','Eventos','Mediana (días)'],rows)+chart+
 p('<span style="color:#13756f">■ Total Pizza</span> · <span style="color:#2457a7">■ Zona Tampa</span> · <span style="color:#cd5d37">■ Zona St. Petersburg</span>')+
 h('Interpretación y cautelas')+p('Kaplan–Meier estima continuidad del seguimiento desde la primera reseña. Los abiertos se censuran a la fecha de corte del dataset; los cerrados usan la última reseña como aproximación de salida. La mediana es el primer tiempo con supervivencia ≤ 0,5 y no se inventa si no se alcanza. Las diferencias entre zonas son descriptivas: no se han calculado intervalos de confianza ni contrastes formales.')+
 p('Yelp no informa apertura real. El parámetro edad_previa_dias permite sensibilidad de entrada tardía; estas consultas usan 0, por lo que no prueban una corrección con edades reales. Tampoco puede interpretarse cada descenso como una fecha exacta de cierre. El tamaño en riesgo disminuye con el tiempo y limita la estabilidad del extremo de la curva.'))

pagina('Visualización en Power BI y consultas',
 p('El equipo abrió LifeMap.pbip en Power BI Desktop, convirtió el mapa Bing a Azure Maps y actualizó las consultas de forma anónima contra http://localhost:5000. Las capturas aportadas muestran las cuatro visualizaciones con datos, incluidos puntos sobre Tampa. La comprobación en Desktop complementa las pruebas estructurales del generador; estas últimas por sí solas no validan el renderizado.')+
 tabla(['Visual','Lectura e interpretación'],[['Mapa de celdas y hotspots','Tamaño por volumen; leyenda de salto; tooltip de negativas ponderadas'],['Tabla de alertas','Probabilidad, umbral, fecha y versión por negocio; indicador proxy'],['Kaplan–Meier','Supervivencia por días para la categoría elegida'],['Evolución','Porcentaje negativo ponderado por reseñas en ventanas cerradas']])+
 h('Alcance espacial y agregación')+p('Parámetros iniciales: Tampa, latitud 27,95; longitud −82,45; radio 5.000 m; categoría Pizza. Mapa, alertas y evolución usan el radio; la curva usa toda la categoría. No deben compararse como si fueran exactamente la misma cohorte. Las consultas espaciales tienen límite de 1.000 registros y fallan explícitamente si lo alcanzan para impedir totales truncados.')+
 p('La medida de negativas calcula Σ(n × pct_negativas) / Σn y convierte la escala 0–100 a proporción antes de mostrar porcentaje. No promedia porcentajes de celdas con volúmenes distintos. La prueba HTTP inicial comprobó 91 ventanas, 99 alertas y 496 puntos KM en ese alcance; son filas de consultas, no los totales globales de MongoDB.')+
 h('Actualización')+p('<b>Verificada: actualización manual con Actualizar.</b> Import en Desktop no hace polling automático. El mecanismo de actualización automática en Power BI Service y su gateway/acceso aún no se han configurado ni demostrado. El dashboard web consulta automáticamente, pero no sustituye ese requisito de Power BI.'))

pagina('Conclusiones, pendientes y fuentes',
 p('La prueba real demuestra la integración de ingesta, inferencia, ventanas, persistencia y visualización. La reproducción pudo acumular retraso y después recuperarse hasta lag cero. Las puntuaciones de riesgo ofrecen señal limitada; el aporte principal comprobado es una plataforma reproducible que permite explorar reputación, ubicación y seguimiento temporal.')+
 h('Reutilización de patrones del semestre')+p('SentimentStream aporta el patrón de preparación de texto e inferencia con un modelo persistido. KafkaMed aporta el patrón de eventos, construcción de variables y alertas mediante foreachBatch. Los ejercicios geoespaciales aportan GeoJSON, índices 2dsphere, $geoNear y $geoWithin; MapReduce se reutiliza para tasas y experimentos de carga. Esta descripción indica patrones técnicos; el equipo debe explicar en la sustentación los cambios concretos respecto a sus ejercicios originales.')+
 tabla(['Pendiente o diferencia','Tratamiento antes de la entrega final'],[['Power BI automático','Configurar mecanismo y demostrar que actualiza sin intervención'],['Servidor separado','El proyecto sigue en el portátil por decisión del equipo; solicitar validación del profesor'],['Disponibilidad 48 horas','Recoger mediciones continuas de la URL; no está demostrada aquí'],['Hotspots y supervivencia','Añadir sensibilidad de umbral y discusión de entrada tardía/muestras'],['Evidencias y sustentación','Conservar capturas, PBIX, artefactos de Jenkins y preparar modificación en vivo']])+
 h('Fuentes y trazabilidad')+p('1. Enunciado LifeMap y diapositivas del curso proporcionados por el equipo: máximo 10 páginas para informe final.<br>2. Yelp Open Dataset, obtenido vía Kaggle: yelp-dataset/yelp-dataset.<br>3. docs/evidencias/build8_resultados.json; preparacion_build13.json; bloqueo_streaming_build14.json.<br>4. Consola Jenkins #19 y conteos MongoDB aportados por el equipo el 7 de noviembre de 2026.<br>5. docs/evidencias/supervivencia_zonas_20261107.json: respuestas API y polígonos reproducibles.<br>6. powerbi/validacion_api.json, proyecto PBIP y capturas Desktop aportadas en la sesión.')+
 p('<b>Estado:</b> informe de avance para revisión; actualizar pendientes y anexar evidencias originales antes de presentarlo como informe final.'))
css='''@page{size:A4;margin:15mm}*{box-sizing:border-box}body{margin:0;color:#17343d;font:10pt/1.4 Arial,sans-serif}section{width:180mm;min-height:265mm;position:relative;padding-bottom:15mm;break-after:page}section:last-child{break-after:auto}.ceja{font-size:8pt;letter-spacing:1px;color:#13756f;border-bottom:2px solid #13756f;padding:5px 0}h1{font-size:21pt;line-height:1.15;margin:16px 0}h2{font-size:12pt;color:#13756f;margin:14px 0 6px}p{margin:8px 0}table{width:100%;border-collapse:collapse;font-size:9pt;margin:10px 0}th,td{border:1px solid #cfdbdf;padding:7px;text-align:left;vertical-align:top}th{background:#eaf4f4}svg{width:100%;max-height:220px}svg text{font:11px Arial}footer{position:absolute;bottom:0;left:0;right:0;border-top:1px solid #cfdbdf;padding-top:6px;font-size:7pt}footer span{float:right}a{color:#13756f}@media screen{body{background:#edf1f3;padding:20px}section{background:#fff;padding:15mm;width:210mm;min-height:297mm;margin:0 auto 20px}footer{left:15mm;right:15mm;bottom:10mm}}'''
(OUT/'informe_avance.html').write_text('<!doctype html><html lang="es"><meta charset="utf-8"><title>LifeMap · Informe de avance</title><style>'+css+'</style><body>'+''.join(pages)+'</body></html>')
print('Informe HTML generado: 7 secciones.')
