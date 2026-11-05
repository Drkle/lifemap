"""Predicción de sentimiento con el PipelineModel de Spark entrenado en spark/jobs/sentimiento.py.

El modelo se carga una sola vez (Spark local dentro del contenedor de la API) y se recarga
si el job de entrenamiento publica una versión nueva en el volumen /models.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

NOMBRES = {0: "negativo", 1: "neutral", 2: "positivo"}


class ModeloNoDisponible(RuntimeError):
    pass


class PredictorSpark:
    def __init__(self, ruta: str):
        self.ruta = Path(ruta)
        self._lock = threading.Lock()
        self._spark = None
        self._modelo = None
        self._marca = None
        self.metadata: dict[str, Any] = {}

    def _marca_actual(self):
        meta = self.ruta / "lifemap_metadata.json"
        return meta.stat().st_mtime if meta.exists() else None

    def estado(self) -> dict[str, Any]:
        marca = self._marca_actual()
        if marca is None:
            return {"disponible": False}
        try:
            meta = json.loads((self.ruta / "lifemap_metadata.json").read_text())
        except (OSError, ValueError):
            return {"disponible": False}
        return {"disponible": True, "modelo": meta.get("modelo_activo"), "version": meta.get("version")}

    def _cargar(self) -> None:
        marca = self._marca_actual()
        if marca is None:
            raise ModeloNoDisponible("El modelo de sentimiento aún no se ha entrenado.")
        if self._modelo is not None and marca == self._marca:
            return
        from pyspark.ml import PipelineModel
        from pyspark.sql import SparkSession

        if self._spark is None:
            self._spark = (
                SparkSession.builder.master("local[1]").appName("lifemap-api-predict")
                .config("spark.ui.enabled", "false")
                .config("spark.driver.memory", "512m")
                .config("spark.sql.shuffle.partitions", "1")
                .getOrCreate()
            )
            self._spark.sparkContext.setLogLevel("ERROR")
        self._modelo = PipelineModel.load(str(self.ruta))
        self.metadata = json.loads((self.ruta / "lifemap_metadata.json").read_text())
        self._marca = marca

    def precargar(self) -> None:
        """Arranca la JVM y carga el modelo en segundo plano (evita ~10 s en la primera petición)."""

        def _tarea():
            try:
                with self._lock:
                    self._cargar()
            except Exception:  # noqa: BLE001 - si aún no hay modelo, se cargará al pedirlo
                pass

        threading.Thread(target=_tarea, daemon=True).start()

    def predecir(self, texto: str) -> dict[str, Any]:
        with self._lock:
            self._cargar()
            df = self._spark.createDataFrame([(texto,)], "texto string")
            fila = self._modelo.transform(df).select("prediction", "probability").first()
        etiqueta = int(fila["prediction"])
        probabilidades = [float(p) for p in fila["probability"]]
        return {
            "sentimiento": NOMBRES[etiqueta],
            "etiqueta": etiqueta,
            "probabilidades": {NOMBRES[i]: round(p, 4) for i, p in enumerate(probabilidades)},
            "modelo": self.metadata.get("modelo_activo"),
            "version_modelo": self.metadata.get("version"),
        }
