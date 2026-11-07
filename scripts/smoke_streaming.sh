#!/usr/bin/env bash
set -euo pipefail
: "${BUILD_NUMBER:?Falta BUILD_NUMBER}"
: "${MONGO_ROOT_PASSWORD:?Falta credencial Mongo}"
case "$BUILD_NUMBER" in *[!0-9]*) echo 'BUILD_NUMBER debe ser numérico'; exit 1;; esac
export KAFKA_TOPIC="ci_reviews_${BUILD_NUMBER}"
export KAFKA_CLASSIFIED_TOPIC="ci_classified_${BUILD_NUMBER}"
export MONGO_DB="ci_lifemap_${BUILD_NUMBER}"
export FECHA_CORTE="${FECHA_CORTE:-2019-01-01}"
export MODELO_PATH="${MODELO_PATH:-/models/sentimiento_v1}"
export RIESGO_PATH="${RIESGO_PATH:-/models/riesgo_v1.json}"
export MANIFEST_PATH="${MANIFEST_PATH:-}"
export FORZAR_FALLO_STREAMING="${FORZAR_FALLO_STREAMING:-false}"
container="lifemap-streaming-smoke-${BUILD_NUMBER}"
cleanup() {
    docker logs --tail 100 "$container" || true
    docker rm -f "$container" >/dev/null 2>&1 || true
    for topic in "$KAFKA_TOPIC" "$KAFKA_CLASSIFIED_TOPIC"; do
        docker compose exec -T kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --delete --if-exists --topic "$topic" || true
    done
    docker run --rm --network lifemap-net -e MONGO_ROOT_USER -e MONGO_ROOT_PASSWORD -e MONGO_DB lifemap-streaming:latest \
        python -c 'from comun import conectar; c,d=conectar(); assert d.name.startswith("ci_lifemap_"); c.drop_database(d.name); c.close()' || true
}
trap cleanup EXIT
for topic in "$KAFKA_TOPIC" "$KAFKA_CLASSIFIED_TOPIC"; do
    docker compose exec -T kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists --topic "$topic" --partitions 3 --replication-factor 1
done
docker run -d --name "$container" --network lifemap-net --memory 2g \
    -e MONGO_ROOT_USER -e MONGO_ROOT_PASSWORD -e MONGO_DB \
    -e KAFKA_TOPIC -e KAFKA_CLASSIFIED_TOPIC -e FECHA_CORTE \
    -e MODELO_PATH -e RIESGO_PATH -e MANIFEST_PATH \
    --tmpfs /checkpoints -v lifemap_modelos:/models:ro lifemap-streaming:latest
docker run --rm --network lifemap-net \
    -e MONGO_ROOT_USER -e MONGO_ROOT_PASSWORD -e MONGO_DB \
    -e KAFKA_TOPIC -e FECHA_CORTE -e MODELO_PATH -e FORZAR_FALLO_STREAMING -v lifemap_modelos:/models:ro lifemap-streaming:latest python smoke.py
