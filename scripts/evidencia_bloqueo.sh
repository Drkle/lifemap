#!/usr/bin/env bash
# Evidencia puntual de que FORZAR_FALLO conserva commit, versión e imagen desplegada.
set -euo pipefail
: "${BUILD_NUMBER:?Falta BUILD_NUMBER}"
case "$BUILD_NUMBER" in ''|*[!0-9]*) echo 'BUILD_NUMBER debe ser numérico' >&2; exit 1;; esac
carpeta=".ci-evidencias/bloqueo-${BUILD_NUMBER}"
mkdir -p "$carpeta"
capturar() {
    local fase="$1"
    curl --fail --silent --show-error --max-time 15 http://api:5000/health > "$carpeta/health-${fase}.json"
    jq -e '(.commit | type == "string") and (.commit != "desconocido") and (.version | type == "string")' "$carpeta/health-${fase}.json" >/dev/null
    jq -cS '{commit,version}' "$carpeta/health-${fase}.json" > "$carpeta/identidad-${fase}.json"
    docker inspect lifemap-api-1 --format '{{.Config.Image}}' > "$carpeta/imagen-${fase}.txt"
    date -u +%Y-%m-%dT%H:%M:%SZ > "$carpeta/fecha-${fase}.txt"
}
case "${1:-}" in
    antes)
        capturar antes
        echo '[bloqueo] Identidad de la API capturada antes de las pruebas.'
        ;;
    despues)
        test -f "$carpeta/identidad-antes.json"
        capturar despues
        cmp "$carpeta/identidad-antes.json" "$carpeta/identidad-despues.json"
        cmp "$carpeta/imagen-antes.txt" "$carpeta/imagen-despues.txt"
        jq -n --arg build "$BUILD_NUMBER" --slurpfile antes "$carpeta/health-antes.json" --slurpfile despues "$carpeta/health-despues.json" \
            '{build_fallido:$build,commit_conservado:($antes[0].commit==$despues[0].commit),version_conservada:($antes[0].version==$despues[0].version),imagen_conservada:true,antes:$antes[0],despues:$despues[0]}' \
            > "$carpeta/resultado.json"
        echo '[bloqueo] OK: el build falló y la API conserva commit, versión e imagen. Consultar los artefactos del build.'
        ;;
    *) echo 'Uso: evidencia_bloqueo.sh antes|despues' >&2; exit 1;;
esac
