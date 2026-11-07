# LifeMap: operación de la segunda entrega

La primera entrega sigue funcionando por defecto. La segunda añade servicios del perfil
`streaming` al mismo Compose, MongoDB y URL. Se necesitan aproximadamente 3 GB adicionales
para Kafka y el consumidor; no basta con que la suma de límites quepa en la RAM del host:
Docker Desktop también necesita memoria para el cliente de ingesta y las construcciones.

## Preparación

En `.env`, usar `DASK_SCHEDULER_MEM=1g`; un `.env` antiguo con 512m anula el nuevo valor
predeterminado. Mantener `.env` fuera de Git. Acordar con el docente las fechas definitivas:
el Word y las diapositivas difieren para la entrega final.

Cortes reproducibles de partida: `FECHA_CORTE=2019-01-01` y
`CORTE_ENTRENAMIENTO=2018-01-01`. Verificar que las cohortes de la región seleccionada tienen
ambas clases; el entrenamiento falla explícitamente si no las tienen.

```bash
# Después de completar la ingesta de la primera entrega:
docker compose exec spark-master spark-submit /opt/jobs/sentimiento.py --fecha-corte 2019-01-01
docker compose build streaming-job
docker compose run --rm streaming-job python entrenar_riesgo.py
docker compose --profile streaming up -d kafka
docker compose --profile streaming run --rm kafka-init
docker compose --profile streaming up -d streaming
# Activar STREAMING_ENABLED=true en .env y recrear la API para incluir Kafka en /health.
docker compose up -d api
docker compose run --rm streaming-job python productor.py --segundos-por-mes 10
```

Estos comandos permiten diagnosticar; la evidencia de entrega debe ser el despliegue
hecho por Jenkins con `ENTREGA2=true`, que ejecuta también la prueba aislada del flujo.
El job sigue llamándose `lifemap-main`. El polling cada 2 minutos respalda el webhook.
Los archivos `config/area.env` y `.env.example` son públicos; las credenciales reales no.

## Aprendizaje y limitaciones

El sentimiento se entrena exclusivamente con reseñas hasta T, y continúa separándose por
negocio. No se reentrena dentro de `foreachBatch`. Riesgo se entrena con variables hasta
el corte anterior, elige umbral en validación de ese periodo y se evalúa en negocios
diferentes al corte T. Su horizonte de entrenamiento debe terminar antes de T.
AUC-PR se compara con la proporción de cierres, no con 0,5. Las métricas solo se publican
cuando las cohortes tienen ambas clases. El JSON en `/models/riesgo_v1.json` contiene
coeficientes, normalización, umbral, cortes, métricas y limitaciones.

Las estrellas y conteos usados como variables vienen de las reseñas anteriores al corte,
no de los totales del snapshot Yelp. Los competidores son de la misma categoría a 500 m,
con primera reseña anterior al corte. Sus fechas reales de apertura y cierre no se conocen.

La API `/survival/<categoria>` usa la última reseña para los cierres y el corte del dataset
para los abiertos censurados. Por defecto mide seguimiento desde la primera reseña. El
parámetro `edad_previa_dias` permite declarar una edad previa estimada para sensibilidad
a entrada tardía: no representa una fecha de apertura observada en Yelp. Devuelve número
en riesgo, cierres, censuras, mediana cuando existe y aviso de grupos menores de 30.
POST admite un Polygon GeoJSON para comparar zonas mediante `$geoWithin`.

## Streaming y recuperación

`reviews` y `reviews_classified` tienen 3 particiones y clave `business_id`. El productor
solo publica fechas posteriores a T en orden ascendente y admite `--limite` y
`--segundos-por-mes`. Espera confirmación del broker para cada mensaje.

El consumidor guarda por `review_id` mediante upsert. Puntúa solo los negocios del
micro-lote y reemplaza su alerta actual (activa o resuelta), con probabilidad y geometría.
El historial del streaming combina reseñas hasta T con reseñas ya reproducidas; no ve las
reseñas futuras que todavía están en el dataset histórico de MongoDB.

Una segunda query deduplica el flujo clasificado y calcula ventanas de 30 días con
watermark de 7 días sobre `date`. Una ventana aparece en MongoDB cuando el watermark la
cierra, no inmediatamente al llegar su primera reseña. El final del dataset puede dejar
la última ventana abierta. Hotspot exige aumento de 15 puntos porcentuales y al menos
20 reseñas en ambas ventanas; son valores iniciales configurables que el informe debe
justificar mediante sensibilidad. Se guardan también ventanas no hotspot para las series.

Los checkpoints persisten en el volumen `checkpoints`. No borrarlos en producción para
"arreglar" errores: hacerlo implica releer Kafka. Si cambian modelo o corte, usar una
nueva revisión de `CHECKPOINT_DIR`; el consumidor rechaza mezclar versiones.

`/health` consulta los offsets finales Kafka y los compara con el último progreso
completado de Spark. Devuelve retraso en mensajes y tiempo desde el progreso observado.
Un consumidor sin progreso reciente se informa como error.

## API adicional

- `GET /live/hotspots?lat=27.95&lon=-82.45&radio=5000&ventana=2019-03-01`
- `GET /alerts?lat=27.95&lon=-82.45&radio=5000`
- `POST /alerts` con Polygon GeoJSON y `?limit=100`.
- `GET /survival/Pizza?edad_previa_dias=0` o POST con Polygon GeoJSON.
- `GET /risk/near?lat=27.95&lon=-82.45&radio=5000`
- `GET /live/windows?lat=27.95&lon=-82.45&radio=5000` para la evolución temporal.

## Pruebas y evidencia

Jenkins con `ENTREGA2=true` construye la imagen, entrena riesgo, crea topics y levanta
un consumidor con base, topics y checkpoints exclusivos de CI. Publica 100 reseñas,
verifica predicciones/probabilidades y versión, las reenvía, verifica riesgo y alerta,
y avanza el watermark para comprobar una ventana con exactamente 100 reseñas únicas.
Los objetos CI se eliminan al terminar, incluso si falla. Un fallo bloquea el despliegue.

Los modelos sintéticos de `streaming/tests/fixture_modelos.py` son exclusivamente fixtures
de integración. No se entregan como modelo entrenado con Yelp ni como resultados propios.

El rollback de `scripts/deploy_api.sh` restaura la imagen API si falla su smoke. No revierte
mutaciones históricas de MongoDB ni modelos reentrenados. Las cargas de esta versión siguen
usando colecciones compartidas: requiere ventana de mantenimiento para recargas y una
futura migración por revisiones si se exige continuidad de datos durante el entrenamiento.
No afirmar en el informe que existe rollback transaccional de toda la plataforma.

## Power BI y sustentación

Importar las consultas de `powerbi/LifeMap.pq` en Power BI Desktop y sustituir el parámetro
BaseUrl con la URL registrada en README. Crear mapa con coordenadas de `Hotspots`, tabla
de `Alertas`, curva con `Supervivencia` y serie temporal de `Ventanas`.
`powerbi/README.md` contiene las medidas y limitaciones de actualización. El archivo PBIX
requiere Power BI Desktop o un servicio compatible; no se ha fabricado un PBIX vacío.
