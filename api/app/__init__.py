"""API Flask de LifeMap.

Patrón application factory: create_app() recibe opcionalmente la base de datos, el
predictor y las sondas; así las pruebas inyectan dobles sin MongoDB, Spark ni Dask.
"""
from flask import Flask, jsonify

from . import config
from .rutas import bp as lifemap_bp
from .rutas_live import bp as live_bp
from .validacion import ErrorValidacion


def create_app(db=None, predictor=None, sondas=None):
    app = Flask(__name__)
    app.json.sort_keys = False

    if db is None:
        from pymongo import MongoClient  # import diferido: las pruebas no necesitan pymongo

        client = MongoClient(config.mongo_uri(), serverSelectionTimeoutMS=3000)
        db = client[config.MONGO_DB]
    if predictor is None:
        from .prediccion import PredictorSpark

        predictor = PredictorSpark(config.MODELO_PATH)
        predictor.precargar()
    if sondas is None:
        from .salud import SONDAS_POR_DEFECTO

        sondas = SONDAS_POR_DEFECTO

    app.config["DB"] = db
    app.config["PREDICTOR"] = predictor
    app.config["SONDAS"] = sondas
    app.register_blueprint(lifemap_bp)
    app.register_blueprint(live_bp)

    @app.get("/health")
    def health():
        """Estado de cada servicio y hash del commit desplegado.

        Devuelve 503 si MongoDB no responde (la API no puede atender nada sin él); si falla
        otro servicio responde 200 con status "degradado" y el detalle.
        """
        servicios = {"api": {"estado": "ok"}}
        try:
            app.config["DB"].command("ping")
            servicios["mongodb"] = {"estado": "ok"}
        except Exception as exc:  # noqa: BLE001 - cualquier fallo de conexión cuenta
            servicios["mongodb"] = {"estado": "error", "detalle": type(exc).__name__}
        for nombre, sonda in app.config["SONDAS"].items():
            servicios[nombre] = sonda()
        if config.STREAMING_ENABLED:
            from .salud import sonda_kafka
            servicios["kafka"] = sonda_kafka(app.config["DB"])
        else:
            servicios["kafka"] = {"estado": "no_aplica", "detalle": "streaming desactivado"}

        mongo_ok = servicios["mongodb"]["estado"] == "ok"
        todos_ok = all(s["estado"] in ("ok", "no_aplica") for s in servicios.values())
        cuerpo = {
            "status": "ok" if todos_ok else ("degradado" if mongo_ok else "error"),
            "commit": config.APP_COMMIT,
            "version": config.APP_VERSION,
            "servicios": servicios,
            "modelo_sentimiento": app.config["PREDICTOR"].estado(),
            "colecciones": {"negocios": config.NEGOCIOS_COLLECTION, "tasas_prefijo": config.TASAS_PREFIX},
        }
        return jsonify(cuerpo), (200 if mongo_ok else 503)

    @app.errorhandler(404)
    def no_encontrado(_):
        return jsonify(error="Ruta no encontrada"), 404

    @app.errorhandler(405)
    def metodo_no_permitido(_):
        return jsonify(error="Método no permitido"), 405

    @app.errorhandler(ErrorValidacion)
    def entrada_invalida(error):
        return jsonify(error=str(error)), 400

    return app
