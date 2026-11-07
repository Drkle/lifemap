#!/usr/bin/env bash
# Solo lectura: no instala paquetes, no crea recursos de nube ni borra datos.
set -euo pipefail
command -v docker >/dev/null || { echo 'Falta instalar Docker Engine.' >&2; exit 1; }
docker info >/dev/null
version=$(docker compose version --short | sed 's/^v//')
minimo=2.24.4
[ "$(printf '%s\n' "$minimo" "$version" | sort -V | head -n1)" = "$minimo" ] || { echo "Compose $version: se requiere >=$minimo" >&2; exit 1; }
mem_kib=$(awk '/MemTotal:/{print $2}' /proc/meminfo)
espacio_kib=$(df -Pk . | awk 'NR==2{print $4}')
[ "$mem_kib" -ge 14680064 ] || { echo 'Se recomiendan 16 GB de RAM; este host tiene menos de 14 GiB disponibles al sistema.' >&2; exit 1; }
[ "$espacio_kib" -ge 31457280 ] || { echo 'Se requieren al menos 30 GiB libres para datos y construcciones.' >&2; exit 1; }
printf 'Preflight OK: Compose %s, RAM %.1f GiB, disco libre %.1f GiB\n' "$version" "$(awk "BEGIN{print $mem_kib/1048576}")" "$(awk "BEGIN{print $espacio_kib/1048576}")"
