from app import create_app, config
from conftest import DBFalsa, PredictorFalso, SONDAS_OK


def test_health_ok_informa_cada_servicio_y_commit(client, monkeypatch):
    r = client.get("/health")
    assert r.status_code == 200
    cuerpo = r.get_json()
    assert cuerpo["status"] == "ok"
    assert cuerpo["commit"] == config.APP_COMMIT
    for servicio in ("api", "mongodb", "spark", "dask", "kafka"):
        assert servicio in cuerpo["servicios"], servicio
    assert cuerpo["servicios"]["dask"]["workers"] == 2
    assert cuerpo["modelo_sentimiento"]["disponible"] is True


def test_health_sin_mongo_responde_503(client_sin_mongo):
    r = client_sin_mongo.get("/health")
    assert r.status_code == 503
    assert r.get_json()["servicios"]["mongodb"]["estado"] == "error"


def test_health_degradado_si_falla_spark():
    sondas = {**SONDAS_OK, "spark": lambda: {"estado": "error", "detalle": "URLError"}}
    app = create_app(db=DBFalsa(), predictor=PredictorFalso(), sondas=sondas)
    r = app.test_client().get("/health")
    assert r.status_code == 200
    assert r.get_json()["status"] == "degradado"


def test_ruta_inexistente_404(client):
    assert client.get("/no-existe").status_code == 404


def test_indice_lista_los_endpoints(client):
    cuerpo = client.get("/").get_json()
    assert len(cuerpo["endpoints"]) == 6


def test_kafka_inactivo_no_se_confunde_con_caida_por_falta_de_mensajes(monkeypatch):
    from datetime import datetime, timezone, timedelta
    from types import SimpleNamespace
    from app.salud import sonda_kafka
    import kafka
    class Consumidor:
        def __init__(self, **kwargs): pass
        def partitions_for_topic(self, nombre): return {0, 1, 2}
        def end_offsets(self, particiones): return {p: 10 for p in particiones}
        def close(self): pass
    monkeypatch.setattr(kafka, 'KafkaConsumer', Consumidor)
    meta={'activo':True,'offsets':{'0':8,'1':9,'2':10},
          'actualizado_en':datetime.now(timezone.utc),
          'progreso_en':datetime.now(timezone.utc)-timedelta(hours=1)}
    db=SimpleNamespace(streaming_meta=SimpleNamespace(find_one=lambda filtro:meta))
    r=sonda_kafka(db)
    assert r['estado']=='ok' and r['retraso_mensajes']==3
    assert r['segundos_desde_progreso']>3500
    meta['actualizado_en']=datetime.now(timezone.utc)-timedelta(seconds=120)
    assert sonda_kafka(db)['estado']=='error'
    meta['actualizado_en']=datetime.now(timezone.utc)
    meta['activo']=False
    assert sonda_kafka(db)['estado']=='error'
    meta['activo']=True
    del meta['offsets']
    assert sonda_kafka(db)['estado']=='error'
