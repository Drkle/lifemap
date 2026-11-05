from app import config
from app.tasas import MIN_DIAS_NEGOCIO_DEFECTO

POLIGONO = {"type": "Polygon", "coordinates": [[[-82.47, 27.94], [-82.45, 27.94], [-82.45, 27.96],
                                               [-82.47, 27.96], [-82.47, 27.94]]]}


def test_near_construye_near_con_parametros(client, db):
    r = client.get("/businesses/near?lat=27.95&lon=-82.45&radio=800&categoria=Pizza&limit=7")
    assert r.status_code == 200
    llamada = db[config.NEGOCIOS_COLLECTION].llamadas[-1]
    filtro = llamada["filtro"]
    assert filtro["location"]["$near"]["$geometry"]["coordinates"] == [-82.45, 27.95]
    assert filtro["location"]["$near"]["$maxDistance"] == 800
    assert filtro["categoria_principal"] == "Pizza"
    assert r.get_json()["parametros"]["limit"] == 7


def test_near_valores_variables_no_fijos(client, db):
    client.get("/businesses/near?lat=10&lon=20&radio=100")
    client.get("/businesses/near?lat=-5&lon=-6&radio=2000")
    filtros = [c["filtro"] for c in db[config.NEGOCIOS_COLLECTION].llamadas]
    assert filtros[0]["location"]["$near"]["$geometry"]["coordinates"] == [20.0, 10.0]
    assert filtros[1]["location"]["$near"]["$maxDistance"] == 2000
    assert "categoria_principal" not in filtros[0]


def test_near_valida_entradas(client):
    assert client.get("/businesses/near?lat=200&lon=0&radio=10").status_code == 400
    assert client.get("/businesses/near?lat=1&lon=1").status_code == 400
    assert client.get("/businesses/near?lat=1&lon=1&radio=-5").status_code == 400
    assert client.get("/businesses/near?lat=1&lon=1&radio=5&categoria=%24where").status_code == 400


def test_within_usa_geowithin(client, db):
    r = client.post("/businesses/within?categoria=Mexican", json=POLIGONO)
    assert r.status_code == 200
    filtro = db[config.NEGOCIOS_COLLECTION].llamadas[-1]["filtro"]
    assert filtro["location"]["$geoWithin"]["$geometry"] == POLIGONO
    assert filtro["categoria_principal"] == "Mexican"


def test_within_rechaza_poligono_abierto(client):
    abierto = {"type": "Polygon", "coordinates": [[[-82, 27], [-81, 27], [-81, 28], [-82, 28]]]}
    assert client.post("/businesses/within", json=abierto).status_code == 400
    assert client.post("/businesses/within", data="no json").status_code == 400


def test_zones_summary_usa_geonear(client, db):
    db[config.NEGOCIOS_COLLECTION].docs = [{"grupo": None, "negocios": 3, "cierres": 1, "dias_negocio": 1095,
                                            "tasa_cierre": 33.3333}]
    r = client.get("/zones/summary?lat=27.95&lon=-82.45&radio=1500&agrupar=categoria&min_dias=1000")
    assert r.status_code == 200
    pipeline = db[config.NEGOCIOS_COLLECTION].llamadas[-1]["pipeline"]
    assert "$geoNear" in pipeline[0]
    assert pipeline[0]["$geoNear"]["maxDistance"] == 1500
    assert pipeline[1]["$group"]["_id"] == "$categoria_principal"
    fila = r.get_json()["resultados"][0]
    assert fila["cumple_minimo"] is True


def test_zones_summary_valida_agrupar(client):
    assert client.get("/zones/summary?lat=1&lon=1&radio=10&agrupar=otro").status_code == 400


def test_stats_closure_filtra_por_minimo(client, db):
    db["tasas_meta"].uno = {"_id": "tasas", "tasa_global": 5.0}
    r = client.get("/stats/closure?por=celda&min_dias=3650&orden=cierres&desc=false&limit=5")
    assert r.status_code == 200
    llamada = db["tasas_celda"].llamadas[-1]
    assert llamada["filtro"] == {"dias_negocio": {"$gte": 3650}}
    assert llamada["sort"] == ("cierres", 1)
    assert r.get_json()["resumen"]["tasa_global"] == 5.0


def test_stats_closure_minimo_por_defecto(client, db):
    client.get("/stats/closure")
    assert db["tasas_categoria"].llamadas[-1]["filtro"] == {"dias_negocio": {"$gte": MIN_DIAS_NEGOCIO_DEFECTO}}


def test_stats_closure_valida(client):
    assert client.get("/stats/closure?por=barrio").status_code == 400
    assert client.get("/stats/closure?orden=$where").status_code == 400
    assert client.get("/stats/closure?min_dias=-1").status_code == 400


def test_predict_post_y_get(client, predictor):
    r = client.post("/predict", json={"texto": "Really bad food"})
    assert r.status_code == 200
    assert r.get_json()["sentimiento"] == "negativo"
    r = client.get("/predict?texto=Great%20pizza")
    assert r.get_json()["sentimiento"] == "positivo"
    assert predictor.textos == ["Really bad food", "Great pizza"]


def test_predict_valida_y_503_sin_modelo(client):
    assert client.post("/predict", json={"texto": "   "}).status_code == 400
    assert client.post("/predict", json={"texto": "x" * 5001}).status_code == 400
    from app import create_app
    from conftest import DBFalsa, PredictorFalso, SONDAS_OK
    sin_modelo = create_app(db=DBFalsa(), predictor=PredictorFalso(disponible=False), sondas=SONDAS_OK)
    assert sin_modelo.test_client().post("/predict", json={"texto": "hola"}).status_code == 503
