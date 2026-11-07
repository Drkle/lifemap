"""Configuración leída del entorno. Ningún valor sensible está escrito en el código."""
import os
from urllib.parse import quote_plus


def mongo_uri() -> str:
    """URI de MongoDB; usuario y contraseña escapados para que @ o : no rompan la URI."""
    if os.getenv("MONGO_URI"):
        return os.environ["MONGO_URI"]
    user = quote_plus(os.getenv("MONGO_ROOT_USER", ""))
    password = quote_plus(os.getenv("MONGO_ROOT_PASSWORD", ""))
    host = os.getenv("MONGO_HOST", "mongodb")
    port = os.getenv("MONGO_PORT", "27017")
    cred = f"{user}:{password}@" if user else ""
    return f"mongodb://{cred}{host}:{port}/?authSource=admin"


MONGO_DB = os.getenv("MONGO_DB", "lifemap")
NEGOCIOS_COLLECTION = os.getenv("NEGOCIOS_COLLECTION", "negocios")
# Staging usa "semilla_" para leer semilla_tasas_* y nunca las tasas reales.
TASAS_PREFIX = os.getenv("TASAS_PREFIX", "")
APP_VERSION = os.getenv("APP_VERSION", "dev")
APP_COMMIT = os.getenv("APP_COMMIT", "desconocido")
SPARK_UI_URL = os.getenv("SPARK_UI_URL", "http://spark-master:8080")
DASK_DASHBOARD_URL = os.getenv("DASK_DASHBOARD_URL", "http://dask-scheduler:8787")
MODELO_PATH = os.getenv("MODELO_PATH", "/models/sentimiento_v1")

STREAMING_ENABLED = os.getenv("STREAMING_ENABLED", "false").lower() == "true"
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
