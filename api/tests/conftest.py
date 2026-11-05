import pytest

from app import create_app
from app.prediccion import ModeloNoDisponible


class CursorFalso(list):
    def __init__(self, docs, registro):
        super().__init__(docs)
        self.registro = registro

    def limit(self, n):
        self.registro["limit"] = n
        return CursorFalso(self[:n], self.registro)

    def sort(self, campo, direccion):
        self.registro["sort"] = (campo, direccion)
        return self


class ColeccionFalsa:
    def __init__(self, docs=None, uno=None):
        self.docs = docs or []
        self.uno = uno
        self.llamadas = []

    def find(self, filtro=None, proyeccion=None):
        registro = {"op": "find", "filtro": filtro, "proyeccion": proyeccion}
        self.llamadas.append(registro)
        return CursorFalso(self.docs, registro)

    def aggregate(self, pipeline):
        self.llamadas.append({"op": "aggregate", "pipeline": pipeline})
        return iter(self.docs)

    def find_one(self, filtro=None):
        self.llamadas.append({"op": "find_one", "filtro": filtro})
        return self.uno


class DBFalsa:
    """Doble de prueba mínimo de una base de datos de pymongo."""

    def __init__(self, disponible=True, colecciones=None):
        self.disponible = disponible
        self.colecciones = colecciones or {}

    def command(self, nombre):
        if not self.disponible:
            raise ConnectionError("MongoDB no disponible")
        return {"ok": 1}

    def __getitem__(self, nombre):
        return self.colecciones.setdefault(nombre, ColeccionFalsa())


class PredictorFalso:
    def __init__(self, disponible=True):
        self.disponible = disponible
        self.textos = []

    def estado(self):
        return {"disponible": self.disponible, "modelo": "naive_bayes", "version": "test"}

    def predecir(self, texto):
        if not self.disponible:
            raise ModeloNoDisponible("El modelo de sentimiento aún no se ha entrenado.")
        self.textos.append(texto)
        negativo = "bad" in texto.lower()
        return {
            "sentimiento": "negativo" if negativo else "positivo",
            "etiqueta": 0 if negativo else 2,
            "probabilidades": {"negativo": 0.9 if negativo else 0.05, "neutral": 0.05,
                               "positivo": 0.05 if negativo else 0.9},
            "modelo": "naive_bayes",
            "version_modelo": "test",
        }


SONDAS_OK = {"spark": lambda: {"estado": "ok", "workers": 1}, "dask": lambda: {"estado": "ok", "workers": 2}}


@pytest.fixture
def db():
    return DBFalsa()


@pytest.fixture
def predictor():
    return PredictorFalso()


@pytest.fixture
def client(db, predictor):
    return create_app(db=db, predictor=predictor, sondas=SONDAS_OK).test_client()


@pytest.fixture
def client_sin_mongo(predictor):
    return create_app(db=DBFalsa(disponible=False), predictor=predictor, sondas=SONDAS_OK).test_client()
