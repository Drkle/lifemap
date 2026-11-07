from datetime import datetime, timedelta
import pytest
from app.analitica import etiqueta_riesgo, fecha_utc, kaplan_meier, probabilidad, variables


def test_variables_no_miran_despues_del_corte():
    t = datetime(2019, 1, 1)
    filas = [{'fecha': t - timedelta(days=10), 'etiqueta': 0, 'estrellas': 1},
             {'fecha': t + timedelta(days=1), 'etiqueta': 2, 'estrellas': 5}]
    v = variables(filas, t, t - timedelta(days=100))
    assert v['n_resenas'] == 1
    assert v['estrellas'] == 1
    assert v['sentimiento_medio'] == -1


def test_etiquetas_excluyen_sin_actividad_y_respetan_horizonte():
    t = datetime(2019, 1, 1)
    assert etiqueta_riesgo({'ultima_resena': t, 'is_open': 0}, t) is None
    assert etiqueta_riesgo({'ultima_resena': t + timedelta(days=100), 'is_open': 0}, t) == 1
    assert etiqueta_riesgo({'ultima_resena': t + timedelta(days=400), 'is_open': 0}, t) == 0
    assert etiqueta_riesgo({'ultima_resena': t + timedelta(days=100), 'is_open': 1}, t) == 0


def test_censurado_sigue_en_riesgo_hasta_corte():
    inicio = datetime(2020, 1, 1)
    cerrado = {'primera_resena': inicio, 'ultima_resena': inicio + timedelta(days=9), 'evento': 1, 'fecha_corte': inicio + timedelta(days=19)}
    abierto = {**cerrado, 'evento': 0, 'ultima_resena': inicio + timedelta(days=2)}
    km = kaplan_meier([cerrado, abierto])
    assert km['curva'][1] == {'dias': 10, 'supervivencia': .5, 'en_riesgo': 2, 'cierres': 1, 'censuras': 0}
    assert km['curva'][2]['dias'] == 20
    assert km['curva'][2]['censuras'] == 1
    assert kaplan_meier([abierto])['mediana_dias'] is None
    assert kaplan_meier([cerrado, abierto], 50)['mediana_dias'] == 60


def test_probabilidad_extrema_es_finita():
    modelo = {'features': ['x'], 'media': [0], 'escala': [1], 'coeficientes': [1000], 'intercepto': 0}
    assert probabilidad(modelo, {'x': 100}) == 1
    assert 0 < probabilidad(modelo, {'x': -100}) < .001


def test_endpoints_live_validan_parametros(client):
    for ruta in ['/alerts', '/risk/near', '/live/hotspots', '/live/windows']:
        assert client.get(ruta).status_code == 400
    assert client.post('/alerts', json={'type': 'Point', 'coordinates': [0, 0]}).status_code == 400
    assert client.get('/survival/Pizza?edad_previa_dias=-1').status_code == 400
    r = client.get('/survival/Pizza')
    assert r.status_code == 200
    assert r.json['n'] == 0


def test_dashboard_se_sirve_y_dependencias_locales(client):
    r = client.get('/dashboard')
    assert r.status_code == 200
    assert b'/static/vendor/leaflet.js' in r.data
    assert client.get('/static/vendor/leaflet.js').status_code == 200
