import json
from pathlib import Path
import pytest
from analitica import FEATURES
from versionado import crear_manifest, comprobar_manifest


@pytest.fixture
def artefactos(tmp_path):
    sentimiento=tmp_path/'sentimiento_e2';sentimiento.mkdir()
    (sentimiento/'lifemap_metadata.json').write_text(json.dumps({'version':'test-e2','fecha_corte':'2019-01-01T00:00:00'}))
    (sentimiento/'weights.bin').write_bytes(b'pesos-de-prueba')
    riesgo=tmp_path/'riesgo.json'
    riesgo.write_text(json.dumps({'version':'test-riesgo','features':list(FEATURES),'media':[0]*6,
        'escala':[1]*6,'coeficientes':[.1]*6,'umbral':.5,'intercepto':0,
        'corte_evaluacion':'2019-01-01T00:00:00','corte_entrenamiento':'2018-01-01T00:00:00'}))
    return sentimiento,riesgo


def test_manifest_detecta_cambios_de_pesos(artefactos,tmp_path):
    s,r=artefactos
    m=crear_manifest(s,r,'2019-01-01','2018-01-01')
    path=tmp_path/'manifest.json';path.write_text(json.dumps(m))
    assert comprobar_manifest(path)==m
    (s/'weights.bin').write_bytes(b'pesos-modificados')
    with pytest.raises(ValueError,match='cambiaron'):
        comprobar_manifest(path)


def test_manifest_rechaza_sentimiento_sin_corte(artefactos):
    s,r=artefactos
    (s/'lifemap_metadata.json').write_text(json.dumps({'version':'e1','fecha_corte':None}))
    with pytest.raises(ValueError,match='sentimiento'):
        crear_manifest(s,r,'2019-01-01','2018-01-01')


def test_manifest_rechaza_riesgo_de_otro_periodo(artefactos):
    s,r=artefactos
    with pytest.raises(ValueError,match='ambos cortes'):
        crear_manifest(s,r,'2019-01-01','2017-01-01')


def test_manifest_rechaza_pesos_invalidos(artefactos):
    s,r=artefactos;m=json.loads(r.read_text());m['escala'][0]=0;r.write_text(json.dumps(m))
    with pytest.raises(ValueError,match='Escala'):
        crear_manifest(s,r,'2019-01-01','2018-01-01')


def test_auditoria_rechaza_fuga_temporal_antes_de_consultar_mongo():
    from preparar_entrega2 import auditar
    with pytest.raises(ValueError,match='horizonte'):
        auditar(None,'2019-01-01','2018-06-01')
