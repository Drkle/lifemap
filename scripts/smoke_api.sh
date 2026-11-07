#!/usr/bin/env bash
# Pruebas contra la API en ejecución (etapas "staging" y "Despliegue" del pipeline).
# Uso: scripts/smoke_api.sh http://api:5000
# Variables:
#   SMOKE_SEMILLA=true         verifica los valores conocidos de negocios_semilla (staging)
#   SMOKE_COMMIT=<hash>        exige que /health informe exactamente ese commit
#   SMOKE_PREDICT_REQUERIDO=true  exige que /predict responda 200 (modelo entrenado)
# Sale con código distinto de 0 si algo falla: eso detiene el pipeline y evita el deploy.
set -euo pipefail
BASE="${1:?Uso: smoke_api.sh <url_base>}"
INTENTOS="${SMOKE_INTENTOS:-30}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

falla() { echo "[smoke] FALLO: $*"; exit 1; }
get() { curl -fsS "$BASE$1" > "$TMP/r.json" || falla "GET $1"; }
codigo() { curl -s -o "$TMP/c.json" -w '%{http_code}' "$@"; }
valor() { jq -r "$1" "$TMP/r.json"; }
es() { jq -e "$1" "$TMP/r.json" > /dev/null || falla "$2"; }

echo "[smoke] esperando a ${BASE}/health ..."
listo=false
for i in $(seq 1 "$INTENTOS"); do
  # /health puede responder 200 degradado mientras arranca el consumidor E2.
  if curl -fsS --connect-timeout 3 --max-time 12 "${BASE}/health" > "$TMP/health.json" 2>/dev/null \
     && jq -e '.status == "ok"' "$TMP/health.json" >/dev/null 2>&1; then
    listo=true
    break
  fi
  if [ "$i" -eq 1 ] || [ "$((i % 5))" -eq 0 ]; then
    echo "[smoke] servicios todavía no listos (${i}/${INTENTOS}); esperando..."
  fi
  sleep "${SMOKE_ESPERA_S:-3}"
done
[ "$listo" = true ] || { cat "$TMP/health.json"; falla "los servicios no alcanzaron estado ok"; }
echo "[smoke] /health -> $(cat "$TMP/health.json")"
[ "$(jq -r .servicios.mongodb.estado "$TMP/health.json")" = "ok" ] || falla "MongoDB no conectado"
for s in spark dask; do
  [ "$(jq -r .servicios.$s.estado "$TMP/health.json")" = "ok" ] || falla "/health: $s no está ok"
done
[ "$(jq -r .status "$TMP/health.json")" = "ok" ] || falla "status != ok"
if [ "${SMOKE_ENTREGA2:-false}" = true ]; then
  [ "$(jq -r .servicios.kafka.estado "$TMP/health.json")" = "ok" ] || falla "Kafka/consumidor no está listo"
fi
if [ -n "${SMOKE_COMMIT:-}" ]; then
  [ "$(jq -r .commit "$TMP/health.json")" = "$SMOKE_COMMIT" ] || falla "/health no informa el commit ${SMOKE_COMMIT}"
fi

[ "$(codigo "${BASE}/ruta-que-no-existe")" = "404" ] || falla "se esperaba 404"
[ "$(codigo "${BASE}/businesses/near?lat=200&lon=0&radio=10")" = "400" ] || falla "/businesses/near inválido debía dar 400"
[ "$(codigo "${BASE}/stats/closure?por=barrio")" = "400" ] || falla "/stats/closure inválido debía dar 400"
[ "$(codigo -X POST "${BASE}/predict" -H 'Content-Type: application/json' --data '{"texto":""}')" = "400" ] \
  || falla "/predict vacío debía dar 400"

cod=$(codigo -X POST "${BASE}/predict" -H 'Content-Type: application/json' \
      --data '{"texto":"The food was amazing and the staff very friendly"}')
if [ "$cod" = "200" ]; then
  echo "[smoke] /predict -> $(cat "$TMP/c.json")"
  jq -e '.sentimiento | IN("negativo","neutral","positivo")' "$TMP/c.json" > /dev/null || falla "/predict sin sentimiento"
elif [ "${SMOKE_PREDICT_REQUERIDO:-false}" = "true" ] || [ "$cod" != "503" ]; then
  falla "/predict respondió ${cod}"
else
  echo "[smoke] /predict -> 503 (modelo aún no entrenado; permitido en este entorno)"
fi

if [ "${SMOKE_SEMILLA:-false}" = "true" ]; then
  C="lat=27.9505&lon=-82.4575&radio=1000"
  get "/businesses/near?${C}&limit=1000"
  es '.total_devuelto == 100' "/businesses/near != 100"
  get "/businesses/near?${C}&limit=1000&categoria=Pizza"
  es '.total_devuelto == 50' "/businesses/near categoria=Pizza != 50"

  poligono='{"type":"Polygon","coordinates":[[[-82.463,27.945],[-82.452,27.945],[-82.452,27.956],[-82.463,27.956],[-82.463,27.945]]]}'
  curl -fsS -X POST "${BASE}/businesses/within?limit=1000" -H 'Content-Type: application/json' \
    --data "$poligono" > "$TMP/r.json" || falla "POST /businesses/within"
  es '.total_devuelto == 100' "/businesses/within != 100"

  get "/zones/summary?${C}"
  es '.resultados[0].negocios == 100' "/zones/summary negocios != 100"
  es '.resultados[0].cierres == 30' "/zones/summary cierres != 30"
  es '.resultados[0].tasa_cierre == 10' "/zones/summary tasa != 10"
  es '.resultados[0].pct_negativas_resenas == 37.5' "/zones/summary % negativas != 37.5"
  get "/zones/summary?${C}&agrupar=categoria"
  es '.total_devuelto == 2' "/zones/summary agrupado != 2 grupos"

  get "/stats/closure?por=categoria&min_dias=0"
  es '.total_devuelto == 2' "/stats/closure categorías != 2"
  [ "$(valor '.resultados[0].categoria')" = "Pizza" ] || falla "la mayor tasa debía ser Pizza"
  es '.resultados[0].tasa_cierre > 13.333 and .resultados[0].tasa_cierre < 13.334' "tasa Pizza != 13.3333"
  get "/stats/closure?por=categoria&min_dias=60000"
  es '.total_devuelto == 0' "el mínimo de días-negocio no filtra"
  get "/stats/closure?por=celda&min_dias=0&limit=5000"
  es '[.resultados[].cierres] | add == 30' "suma de cierres por celda != 30"
  [ "$(valor '.resultados[0].geometry.type')" = "Polygon" ] || falla "celda sin geometría"
  echo "[smoke] semilla: near 100/50, within 100, zona 100/30/10 %, Pizza 13,333 %, celdas suman 30 OK"
fi

if [ "${SMOKE_ENTREGA2:-false}" = true ]; then
  C="lat=27.9505&lon=-82.4575&radio=5000"
  for ruta in "/live/hotspots?${C}" "/alerts?${C}" "/risk/near?${C}"; do
    get "$ruta"
    es '(.resultados | type) == "array"' "$ruta sin resultados válidos"
  done
  get "/survival/Pizza"
  es '(.curva | type) == "array" and (.n | type) == "number"' "curva de supervivencia inválida"
  echo '[smoke] E2: Kafka/consumidor y los cuatro endpoints nuevos OK'
fi

echo "[smoke] OK"
