"""Descarga idempotente del Yelp Open Dataset desde Kaggle.

Solo se descargan los dos archivos que usa LifeMap (business y review); el resto del
dataset (user, tip, checkin) suma varios GB que no se necesitan.
"""

from __future__ import annotations

import json
import os
import subprocess
import zipfile
from pathlib import Path


DATA_ROOT = Path("/data/raw")
ARCHIVOS = {
    "business": "yelp_academic_dataset_business.json",
    "review": "yelp_academic_dataset_review.json",
}


def _directorio_dataset(slug: str, root: Path = DATA_ROOT) -> Path:
    return root / slug.replace("/", "__")


def _inventario(directorio: Path) -> list[dict[str, object]]:
    return [
        {"nombre": str(path.relative_to(directorio)), "bytes": path.stat().st_size}
        for path in sorted(directorio.rglob("*"))
        if path.is_file() and path.name != ".descarga_ok"
    ]


def _cache_valida(directorio: Path) -> bool:
    marcador = directorio / ".descarga_ok"
    if not marcador.exists():
        return False
    try:
        esperado = json.loads(marcador.read_text(encoding="utf-8"))["archivos"]
    except (OSError, KeyError, json.JSONDecodeError):
        return False
    return esperado == _inventario(directorio) and bool(esperado)


def _descomprimir(directorio: Path) -> None:
    for comprimido in directorio.glob("*.zip"):
        print(f"[descarga] descomprimiendo {comprimido.name} ...")
        with zipfile.ZipFile(comprimido) as zf:
            zf.extractall(directorio)
        comprimido.unlink()


def _kaggle(argumentos: list[str], token: str) -> None:
    resultado = subprocess.run(["kaggle", *argumentos], capture_output=True, text=True, check=False)
    if resultado.returncode != 0:
        detalle = (resultado.stderr or resultado.stdout or "error desconocido")
        if token:
            detalle = detalle.replace(token, "***")
        ultima = detalle.strip().splitlines()[-1] if detalle.strip() else "error desconocido"
        raise RuntimeError(f"Kaggle falló ({' '.join(argumentos[:3])}): {ultima}")


def descargar_dataset(slug: str, root: Path = DATA_ROOT) -> dict[str, Path]:
    """Descarga (si hace falta) y devuelve las rutas de business y review.

    El valor de ``KAGGLE_API_TOKEN`` nunca aparece en los mensajes de error.
    """

    directorio = _directorio_dataset(slug, root)
    directorio.mkdir(parents=True, exist_ok=True)

    if _cache_valida(directorio):
        print(f"[descarga] caché válida: {directorio}")
    else:
        token = os.getenv("KAGGLE_API_TOKEN", "")
        if not token and not os.getenv("KAGGLE_KEY"):
            raise RuntimeError(
                "Falta KAGGLE_API_TOKEN. Configurar la credencial 'kaggle-api-token' en Jenkins."
            )
        for nombre in ARCHIVOS.values():
            if (directorio / nombre).exists():
                continue
            print(f"[descarga] descargando {nombre} de {slug} ...")
            _kaggle(["datasets", "download", "-d", slug, "-f", nombre, "-p", str(directorio)], token)
            _descomprimir(directorio)
        faltan = [n for n in ARCHIVOS.values() if not (directorio / n).exists()]
        if faltan:
            raise RuntimeError(f"Kaggle no produjo los archivos esperados: {faltan}")
        (directorio / ".descarga_ok").write_text(
            json.dumps({"dataset": slug, "archivos": _inventario(directorio)}, indent=2),
            encoding="utf-8",
        )

    rutas = {clave: directorio / nombre for clave, nombre in ARCHIVOS.items()}
    for clave, ruta in rutas.items():
        print(f"[descarga] {clave}: {ruta.name} ({ruta.stat().st_size:,} bytes)")
    return rutas
