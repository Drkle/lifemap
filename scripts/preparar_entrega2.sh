#!/usr/bin/env bash
# Construye y prueba candidatos E2 en carpetas separadas; no cambia API/consumidor.
set -euo pipefail
. jenkins/ci-env.sh
export MODELO_PATH=/models/entrega2/sentimiento_e2_v1
export RIESGO_PATH=/models/entrega2/riesgo_v1.json
export MANIFEST_PATH=/models/entrega2/manifest.json
: "${BUILD_NUMBER:?Falta BUILD_NUMBER}"
case "$BUILD_NUMBER" in ''|*[!0-9]*) echo 'BUILD_NUMBER debe ser numérico'; exit 1;; esac
evidencias=".ci-evidencias/entrega2-${BUILD_NUMBER}"
mkdir -p "$evidencias"

# Si E2 ya está activa, no sobrescribir los modelos que esa API está leyendo.
activa=$(docker inspect --format '{{range .Config.Env}}{{if eq . "STREAMING_ENABLED=true"}}true{{end}}{{end}}' lifemap-api-1 2>/dev/null || true)
if [ "$activa" = true ]; then
    if [ "${ENTRENAR_MODELO:-false}" = true ] || [ "${ENTRENAR_RIESGO:-false}" = true ]; then
        echo 'No se reentrenan artefactos activos en su propia carpeta. Preparar una nueva revisión antes de cambiar modelos.' >&2
        exit 1
    fi
    docker compose run --rm --no-deps streaming-job python -c 'import json,os; from pathlib import Path; from analitica import fecha_utc; m=json.loads(Path(os.environ["MANIFEST_PATH"]).read_text()); assert m["fecha_corte"]==fecha_utc(os.environ["FECHA_CORTE"]).isoformat() and m["corte_entrenamiento"]==fecha_utc(os.environ["CORTE_ENTRENAMIENTO"]).isoformat(), "No cambiar cortes de modelos activos en la misma carpeta"'
fi

docker compose exec -T spark-master cat /models/sentimiento_v1/lifemap_metadata.json > "$evidencias/modelo_e1_antes.json"
docker compose build streaming-job
docker compose run --rm --no-deps streaming-job python -m pytest -q tests
# El comando es de solo lectura sobre MongoDB: fechas, reservas, clases y cohortes.
docker compose run --rm --no-deps streaming-job python preparar_entrega2.py | tee "$evidencias/auditoria.json"

if [ "${ENTRENAR_MODELO:-false}" = true ] || ! docker compose run --rm --no-deps streaming-job python -c 'import json,os,sys; from pathlib import Path; from analitica import fecha_utc; p=Path(os.environ["MODELO_PATH"])/"lifemap_metadata.json"; m=json.loads(p.read_text()) if p.exists() else {}; sys.exit(0 if m.get("fecha_corte")==fecha_utc(os.environ["FECHA_CORTE"]).isoformat() else 1)'; then
    docker compose exec -T spark-master spark-submit /opt/jobs/sentimiento.py \
        --coleccion resenas --fecha-corte "${FECHA_CORTE}" --salida /models/entrega2 --nombre-modelo sentimiento_e2_v1
fi
if [ "${ENTRENAR_RIESGO:-false}" = true ] || ! docker compose run --rm --no-deps streaming-job python -c 'import json,os,sys; from pathlib import Path; from analitica import fecha_utc; p=Path(os.environ["RIESGO_PATH"]); m=json.loads(p.read_text()) if p.exists() else {}; sys.exit(0 if m.get("corte_evaluacion")==fecha_utc(os.environ["FECHA_CORTE"]).isoformat() and m.get("corte_entrenamiento")==fecha_utc(os.environ["CORTE_ENTRENAMIENTO"]).isoformat() else 1)'; then
    docker compose run --rm --no-deps streaming-job python entrenar_riesgo.py --sin-publicar-scores
fi
docker compose run --rm --no-deps streaming-job python versionado.py | tee "$evidencias/manifest.json"
# Copia solo métricas revisables; no incluye credenciales ni textos de Yelp.
docker compose run --rm --no-deps streaming-job python -c 'import os; from pathlib import Path; print(Path(os.environ["RIESGO_PATH"]).read_text())' > "$evidencias/riesgo_metricas.json"
docker compose run --rm --no-deps streaming-job python -c 'import os; from pathlib import Path; print((Path(os.environ["MODELO_PATH"])/"lifemap_metadata.json").read_text())' > "$evidencias/sentimiento_metricas.json"

docker compose --profile streaming up -d --wait kafka
docker compose --profile streaming run --rm kafka-init
bash scripts/smoke_streaming.sh | tee "$evidencias/smoke.log"
# Confirma que los artefactos no se modificaron durante la prueba.
docker compose run --rm --no-deps streaming-job python versionado.py --comprobar > /dev/null
docker compose exec -T spark-master cat /models/sentimiento_v1/lifemap_metadata.json > "$evidencias/modelo_e1_despues.json"
cmp "$evidencias/modelo_e1_antes.json" "$evidencias/modelo_e1_despues.json"
echo '[entrega2] Preparación aprobada: modelos separados, cortes auditados y smoke validado.'
