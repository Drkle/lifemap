"""
Prueba de integración Dask <-> MongoDB.

1. Se conecta al scheduler y espera a que haya al menos 2 workers.
2. Ejecuta un cálculo distribuido y comprueba en qué workers corrió.
3. Hace ping a MongoDB y cuenta negocios_semilla (100 documentos esperados).

Ejecutar:
  docker compose run --rm dask-job python check_cluster.py
"""
import os
import sys
from urllib.parse import quote_plus

import dask.array as da
from dask.distributed import Client
from pymongo import MongoClient

MIN_WORKERS = int(os.getenv("DASK_MIN_WORKERS", "2"))


def mongo_uri():
    user = quote_plus(os.getenv("MONGO_ROOT_USER", ""))
    password = quote_plus(os.getenv("MONGO_ROOT_PASSWORD", ""))
    host, port = os.getenv("MONGO_HOST", "mongodb"), os.getenv("MONGO_PORT", "27017")
    return f"mongodb://{user}:{password}@{host}:{port}/?authSource=admin"


def main():
    client = Client(os.getenv("DASK_SCHEDULER", "tcp://dask-scheduler:8786"), timeout=30)
    client.wait_for_workers(MIN_WORKERS, timeout=60)
    workers = list(client.scheduler_info()["workers"])
    print(f"[check] workers conectados: {len(workers)}")

    x = da.random.random((4000, 4000), chunks=(1000, 1000))
    fut = client.compute(x.mean())
    media = fut.result()
    print(f"[check] cálculo distribuido OK (media={media:.4f}, esperada ~0.5)")

    mongo = MongoClient(mongo_uri(), serverSelectionTimeoutMS=5000)
    mongo.admin.command("ping")
    n = mongo[os.getenv("MONGO_DB", "lifemap")]["negocios_semilla"].count_documents({})
    print(f"[check] MongoDB OK, negocios_semilla = {n}")

    ok = len(workers) >= MIN_WORKERS and abs(media - 0.5) < 0.01 and n == 100
    print("[check] RESULTADO:", "OK" if ok else "FALLO")
    client.close()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
