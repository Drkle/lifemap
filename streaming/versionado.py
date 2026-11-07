"""Manifiesto verificable de modelos de E2, sin sustituir el modelo de E1."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from analitica import fecha_utc, FEATURES


def huella_archivo(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as f:
        for parte in iter(lambda:f.read(1024*1024), b''):
            digest.update(parte)
    return digest.hexdigest()


def huella_directorio(path):
    raiz=Path(path); digest=hashlib.sha256()
    archivos=sorted(p for p in raiz.rglob('*') if p.is_file())
    if not archivos:
        raise ValueError('Modelo de sentimiento vacío')
    for p in archivos:
        digest.update(p.relative_to(raiz).as_posix().encode());digest.update(b'\0')
        digest.update(huella_archivo(p).encode())
    return digest.hexdigest()


def crear_manifest(sentimiento, riesgo, corte, entrenamiento):
    sentimiento,riesgo=Path(sentimiento),Path(riesgo)
    meta=json.loads((sentimiento/'lifemap_metadata.json').read_text())
    r=json.loads(riesgo.read_text())
    if meta.get('fecha_corte') != fecha_utc(corte).isoformat() or not meta.get('version'):
        raise ValueError('El modelo de sentimiento no corresponde al corte solicitado')
    if r.get('corte_evaluacion') != fecha_utc(corte).isoformat() or r.get('corte_entrenamiento') != fecha_utc(entrenamiento).isoformat():
        raise ValueError('El modelo de riesgo no corresponde a ambos cortes solicitados')
    if r.get('features') != list(FEATURES):
        raise ValueError('Variables del modelo de riesgo incompatibles')
    for campo in ('media','escala','coeficientes'):
        if len(r[campo])!=len(FEATURES) or not all(math.isfinite(x) for x in r[campo]):
            raise ValueError('Parámetros de riesgo inválidos')
    if not r.get('version') or not math.isfinite(r['intercepto']) or not all(x>0 for x in r['escala']) or not 0<=r['umbral']<=1:
        raise ValueError('Escala o umbral inválidos')
    contenido={'fecha_corte':meta['fecha_corte'],'corte_entrenamiento':r['corte_entrenamiento'],
        'sentimiento':{'ruta':str(sentimiento),'version':meta['version'],'sha256':huella_directorio(sentimiento)},
        'riesgo':{'ruta':str(riesgo),'version':r['version'],'sha256':huella_archivo(riesgo)}}
    contenido['revision']=hashlib.sha256(json.dumps(contenido,sort_keys=True).encode()).hexdigest()[:16]
    return contenido


def comprobar_manifest(path):
    m=json.loads(Path(path).read_text())
    nuevo=crear_manifest(m['sentimiento']['ruta'],m['riesgo']['ruta'],m['fecha_corte'],m['corte_entrenamiento'])
    if m!=nuevo:
        raise ValueError('Los modelos cambiaron desde que se guardó el manifiesto')
    return m


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--comprobar',action='store_true')
    p.add_argument('--revision',action='store_true')
    p.add_argument('--salida',default=os.getenv('MANIFEST_PATH','/models/entrega2/manifest.json'))
    a=p.parse_args()
    if a.comprobar:
        m=comprobar_manifest(a.salida)
    else:
        m=crear_manifest(os.getenv('MODELO_PATH','/models/entrega2/sentimiento_e2_v1'),
            os.getenv('RIESGO_PATH','/models/entrega2/riesgo_v1.json'),os.getenv('FECHA_CORTE','2019-01-01'),os.getenv('CORTE_ENTRENAMIENTO','2018-01-01'))
        pth=Path(a.salida);pth.parent.mkdir(parents=True,exist_ok=True)
        temporal=pth.with_suffix('.tmp');temporal.write_text(json.dumps(m,ensure_ascii=False,indent=2));temporal.replace(pth)
    print(m['revision'] if a.revision else json.dumps(m,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
