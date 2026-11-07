# LifeMap: reputación, ubicación y supervivencia de negocios

Curso Big Data · Institución Universitaria de Envigado · 2026-2

**URL pública del sistema:** `https://aviation-decrease-hunger.ngrok-free.dev`
(`/health` muestra el estado de cada servicio y el commit desplegado)

Sistema que mide cuánto viven los negocios de un área metropolitana del Yelp Open Dataset,
qué dice su reputación (sentimiento de las reseñas) y dónde se concentra el riesgo de cierre,
consultable por ubicación. Entrega 1: plataforma batch, sentimiento y tasas de cierre.

| | |
|---|---|
| Área y familia | `config/area.env` (por defecto **FL = Tampa**, **Restaurants**) |
| Datos | Yelp Open Dataset en Kaggle (`yelp-dataset/yelp-dataset`): `business.json` y `review.json` |
| Tecnologías | Dask, Spark (MLlib, RDD), MongoDB (GeoJSON + 2dsphere), Flask, Docker Compose, Jenkins, ngrok |

## Arquitectura

```text
 GitHub ──webhook──▶ smee.io ──▶ Jenkins (socket de Docker) ── build → pytest → staging → deploy
                                       │
 ┌────────────────────────── docker compose (red lifemap-net) ───────────────────────────────┐
 │  Kaggle API ─▶ volumen kaggle_data ─▶ Dask (scheduler + 2 workers) ──lotes──▶ MongoDB     │
 │                                        limpieza N1–N7 / R1–R5,          negocios (GeoJSON,│
 │                                        vida de cada negocio             2dsphere), resenas│
 │                                                                              ▲   ▲        │
 │  Spark (master + worker, MongoDB Spark Connector) ◀──────────────────────────┘   │        │
 │     sentimiento (TF-IDF + NB / LR) ─▶ volumen modelos                            │        │
 │     MapReduce tasas de cierre ─▶ tasas_categoria, tasas_celda ───────────────────┘        │
 │     balanceo 2/8/32/200 particiones ─▶ balanceo_*                                         │
 │  Flask API ($near, $geoWithin, $geoNear, /predict con el modelo) ◀── ngrok ◀── internet   │
 └───────────────────────────────────────────────────────────────────────────────────────────┘
```

| Carpeta | Contenido |
|---|---|
| `ingest/` | Descarga de Kaggle, limpieza (`limpieza.py`), pipeline Dask (`pipeline_ingesta.py`), geohash |
| `spark/jobs/` | `sentimiento.py`, `tasas_mapreduce.py`, `balanceo.py`, `verificar_semilla.py`, `check_conexion.py` |
| `api/` | Flask: 6 endpoints, validación, pruebas |
| `mongo/init/` | Validador GeoJSON, índices 2dsphere y semilla determinista para las pruebas |
| `scripts/smoke_api.sh` | Pruebas contra la API desplegada (staging y producción) |
| `config/area.env` | Área y familia de categorías del equipo (sin secretos) |

## Puesta en marcha desde cero

Requisitos del servidor: Docker con Compose v2, unos **16 GB de RAM** (con 8 GB bajar los límites en
`.env`), unos **25 GB de disco** (el `review.json` de Yelp pesa ~5 GB) y salida a internet.

```bash
git clone https://github.com/Drkle/lifemap.git && cd lifemap
cp .env.example .env          # editar: MONGO_ROOT_PASSWORD, KAGGLE_API_TOKEN, NGROK_*, SMEE_URL
# (opcional) editar config/area.env con el área y la familia asignadas

# 1. Servicios (MongoDB crea los índices y la semilla al iniciar su volumen)
docker compose up -d --build --wait

# 2. Ingesta con Dask: descarga Yelp desde Kaggle, limpia, construye la vida y carga por lotes
docker compose run --rm dask-job python pipeline_ingesta.py

# 3. Spark: tasas de cierre (MapReduce), modelo de sentimiento y balanceo
docker compose exec spark-master spark-submit /opt/jobs/tasas_mapreduce.py
docker compose exec spark-master spark-submit /opt/jobs/sentimiento.py
docker compose exec spark-master spark-submit /opt/jobs/balanceo.py

# 4. URL pública (ngrok, dominio estático gratuito de la cuenta)
docker compose --profile public up -d ngrok

# 5. CI/CD
docker compose --profile ci up -d --build jenkins smee
```

En Windows con PowerShell, los mismos comandos funcionan con Docker Desktop. Los secretos solo
viven en `.env` (ignorado por git) y en las credenciales de Jenkins.

### Jenkins

1. Abrir `http://localhost:8080`, completar el asistente
   (`docker compose exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword`).
2. Credenciales globales: `mongo-root` (*Username with password*, los mismos valores de `.env`) y
   `kaggle-api-token` (*Secret text*).
3. Crear un job *Pipeline* llamado exactamente **`lifemap-main`** → *Pipeline script from SCM* →
   Git → este repositorio → rama `*/main` → *Script Path* `Jenkinsfile`; activar
   *GitHub hook trigger for GITScm polling*.
4. Webhook: crear un canal en <https://smee.io>, ponerlo en `SMEE_URL` y en GitHub
   (*Settings → Webhooks*, `application/json`, evento *push*). El `Jenkinsfile` incluye también
   `pollSCM('H/2 * * * *')` como respaldo cada 2 minutos, permitido por el enunciado.
5. Prueba de bloqueo: lanzar el job con **FORZAR_FALLO = true**. Falla `pytest`, no se ejecuta el
   despliegue y `/health` sigue mostrando el commit anterior. Ese build queda en el historial.

Etapas: checkout → construir imágenes (el hash del commit se graba en la API) → pytest (API,
ingesta y Spark, incluida la fórmula de la tasa) → acceso a Kaggle → levantar servicios →
ingesta idempotente → integración Dask/Spark → **Spark sobre la semilla con valores conocidos** →
Spark real → API candidata en staging + smoke → **despliegue** → verificación de `/health` y del commit.

## API

| Método y ruta | Parámetros | Consulta MongoDB |
|---|---|---|
| `GET /health` | — | estado de MongoDB, Spark, Dask, API y commit |
| `GET /businesses/near` | `lat`, `lon`, `radio` (m), `categoria?`, `limit?` | `$near` |
| `POST /businesses/within` | cuerpo: `Polygon` GeoJSON; `?categoria`, `?limit` | `$geoWithin` |
| `GET /zones/summary` | `lat`, `lon`, `radio`, `categoria?`, `agrupar=categoria?`, `min_dias?` | `$geoNear` + `$group` |
| `GET /stats/closure` | `por=categoria\|celda`, `min_dias?`, `orden?`, `desc?`, `limit?` | colecciones de Spark |
| `POST /predict` | `{"texto": "..."}` (también `GET ?texto=`) | modelo de Spark guardado |

```bash
URL=https://aviation-decrease-hunger.ngrok-free.dev
curl "$URL/health"
curl "$URL/businesses/near?lat=27.9506&lon=-82.4572&radio=1000&categoria=Pizza&limit=5"
curl -X POST "$URL/businesses/within?limit=20" -H 'Content-Type: application/json' \
  -d '{"type":"Polygon","coordinates":[[[-82.47,27.94],[-82.44,27.94],[-82.44,27.97],[-82.47,27.97],[-82.47,27.94]]]}'
curl "$URL/zones/summary?lat=27.9506&lon=-82.4572&radio=2000&agrupar=categoria"
curl "$URL/stats/closure?por=categoria&min_dias=18250&limit=10"
curl -X POST "$URL/predict" -H 'Content-Type: application/json' -d '{"texto":"Cold food and rude staff"}'
```

## Definiciones y decisiones

- **Etiqueta de sentimiento:** 1–2 estrellas = negativo, 3 = neutral, 4–5 = positivo. La
  distribución (desbalanceada) queda en el reporte de ingesta y en `modelo_metricas`.
- **Vida de un negocio:** de la primera a la última reseña, contando ambos días. Es una
  aproximación porque Yelp no trae fechas de apertura ni de cierre: subestima la vida (la
  apertura es anterior a la primera reseña: **entrada tardía**) y, en los cerrados, el cierre
  real puede ser posterior a la última reseña.
- **Evento y censura:** `is_open = 0` es un cierre observado; `is_open = 1` es censura (solo se
  sabe que seguía abierto en la fecha de corte = última reseña del dataset completo). También se
  guarda `dias_hasta_corte` para discutir la exposición de los censurados.
- **Tasa de cierre anualizada:** `cierres ÷ (días-negocio ÷ 365) × 100`, la misma AFR del
  ejercicio de discos (`spark/jobs/tasas.py`, con su prueba en el pipeline).
- **Mínimo de días-negocio:** 18.250 (50 años-negocio) por defecto. Con 50 años-negocio, un cierre
  más mueve la tasa 2 puntos; por debajo, la tasa de un grupo depende de uno o dos cierres. Es un
  parámetro (`min_dias`) en la API y en `tasas_mapreduce.py`.
- **Celda espacial:** geohash de 6 caracteres (~1,2 × 0,6 km), con su polígono GeoJSON.
- **Partición sin fuga:** `|hash(business_id)| % 10 ∈ {8, 9}` = prueba; el job verifica que
  ningún negocio quede en entrenamiento y prueba. Las clases se ponderan por frecuencia inversa.
- **Limpieza:** reglas N1–N7 (negocios) y R1–R5 (reseñas) en `ingest/limpieza.py`; los conteos
  antes y después de cada una quedan en `/data/reporte_limpieza.json` y en `ingesta_meta`.

## Evidencias para el informe

```bash
docker compose exec dask-scheduler cat /data/reporte_limpieza.json          # conteos de limpieza
docker compose exec spark-master cat /models/metricas_sentimiento.json      # NB vs LR por clase
docker compose cp spark-master:/data/evidencias ./docs/evidencias           # balanceo (CSV)
curl "$URL/stats/closure?por=categoria&limit=20"                            # tasas de cierre
```

## Pruebas

```bash
cd api && pytest -q                     # API (incluye la fórmula de la tasa)
cd ingest && pytest -q                  # limpieza, vida, geohash
docker run --rm --entrypoint spark-submit lifemap-spark --master local[2] /opt/tests/test_spark.py
```

Fuente de los datos: Yelp Open Dataset (Yelp Inc.), distribuido en Kaggle; se usa según sus
términos de uso con fines académicos. Partes de la infraestructura provienen de los trabajos
previos del equipo (Big Data geoespacial y "¿Cuánto viven los discos?").

## Segunda entrega y dashboard

El dashboard web está disponible en `/dashboard` y se actualiza cada 15 segundos.
La [guía de operación de la segunda entrega](docs/ENTREGA2.md) documenta el perfil Kafka,
los cortes temporales, los modelos, checkpoints, endpoints y prueba de humo aislada.
Las [consultas de Power BI](powerbi/README.md) permiten conectar las cuatro visualizaciones.

Para Jenkins de la primera entrega, mantener `ENTREGA2=false`. Para la segunda,
activar `ENTREGA2=true` después de tener ingesta válida y recursos suficientes. Los cortes
son parámetros del job. No confundir código implementado con evidencia de un build verde:
la entrega exige su ejecución en el servidor externo con Yelp y URL pública.

**Corrección de Dask:** al actualizar un entorno existente, cambiar también
`DASK_SCHEDULER_MEM=1g` en su `.env`. Un valor antiguo de 512m tiene prioridad sobre Compose.
El diccionario de negocios viaja como argumento reconstruible del grafo Dask, sin depender de un Future de scatter que se pierda al reiniciar workers.
Jenkins limita la ingesta a dos tareas activas, bloques de 16 MB y un hilo por worker.
Si falla, el post del pipeline recoge estados, reinicios y logs de Dask automáticamente.

**Alcance del rollback:** el despliegue restaura la imagen anterior de API cuando falla su
verificación. No es un rollback transaccional de los datos o los modelos compartidos.
La recarga de datos requiere una ventana de mantenimiento; no ejecutar dos jobs sobre los
mismos contenedores y volúmenes a la vez.

Para generar un informe base con evidencia de las ejecuciones reales (falla si falta alguna):

```bash
docker compose run --rm -e GIT_COMMIT dask-job python informe.py --url https://aviation-decrease-hunger.ngrok-free.dev
docker compose cp dask-worker-1:/data/evidencias ./docs/evidencias
```

Revisar la interpretación y maquetar el informe a un máximo de 6 páginas. La exportación
no sustituye el historial de builds, la URL disponible ni la sustentación del equipo.

## Informe de la primera entrega y evidencia del build #8

[PDF de seis páginas y fuentes](docs/entrega1/README.md), con limpieza, comparación NB/LR,
tasas, balanceo y comprobación pública de los seis endpoints. El documento identifica lo
estado: bloqueo confirmado en el build #10; presentación acordada en el mismo portátil;
disponibilidad pendiente de registro.
El parámetro FORZAR_FALLO captura ahora la identidad de la API antes/después y publica
artefactos del build. La [guía de traslado](deploy/SERVIDOR.md) incluye un override para que
los puertos administrativos se limiten a loopback y un preflight sin cambios en el host.

**Plan de presentación acordado:** se seguirá desarrollando y mostrando LifeMap en el mismo
portátil con Docker/Jenkins/ngrok. No hay traslado de máquina en el plan activo. El informe
explica la diferencia con el enunciado. El build #10 demostró bloqueo del despliegue ante el
fallo intencional, conservando la API versión 9; ver `docs/evidencias/bloqueo_build10.json`.
