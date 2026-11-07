#!/usr/bin/env bash
# Restaura la imagen de API anterior si falla el smoke posterior al reemplazo.
set -euo pipefail
. jenkins/ci-env.sh
: "${API_TAG:?Falta API_TAG}"
anterior=$(docker inspect lifemap-api-1 --format '{{.Config.Image}}' 2>/dev/null || true)
docker compose up -d --no-deps --no-build api
if SMOKE_COMMIT="${GIT_COMMIT}" SMOKE_PREDICT_REQUERIDO=true bash scripts/smoke_api.sh http://api:5000; then
    echo "API desplegada: ${API_TAG} (${GIT_COMMIT})"
    exit 0
fi
echo 'Falló la verificación de la API nueva; restaurando imagen anterior.' >&2
case "$anterior" in
    lifemap-api:*) API_TAG="${anterior#lifemap-api:}" docker compose up -d --no-deps --no-build api ;;
    '') docker compose stop api ;;
    *) echo "No se reconoce la imagen previa; requiere revisión del operador." >&2 ;;
esac
exit 1
