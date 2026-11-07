"""Ejecuta deploy_api.sh real con Docker/smoke simulados, sin acceder al host Docker."""
import json
import os
import subprocess
import sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('smoke_ok',[True,False])
def test_deploy_restaura_imagen_modelo_y_modo_si_falla(tmp_path,smoke_ok):
    binario=tmp_path/'bin';binario.mkdir();log=tmp_path/'docker.jsonl'
    docker=binario/'docker'
    docker.write_text(f'#!{sys.executable}\n'+'''import os,sys,json
args=sys.argv[1:]
if args[0]=='inspect':
    formato=args[args.index('--format')+1]
    if '.Config.Image' in formato: print('lifemap-api:12')
    elif 'MODELO_PATH' in formato: print('MODELO_PATH=/models/sentimiento_v1')
    else: print('')
elif args[:2]==['compose','up']:
    with open(os.environ['TEST_DEPLOY_LOG'],'a') as f:
        f.write(json.dumps({k:os.environ.get(k) for k in ['API_TAG','MODELO_PATH','STREAMING_ENABLED']})+'\\n')
''')
    bash=binario/'bash'
    bash.write_text(f'#!{sys.executable}\nimport os,sys\nassert sys.argv[1]=="scripts/smoke_api.sh"\nsys.exit(int(os.environ["TEST_SMOKE_RESULT"]))\n')
    docker.chmod(0o755);bash.chmod(0o755)
    env={**os.environ,'PATH':str(binario)+':'+os.environ['PATH'],'MONGO_CRED_USR':'fixture',
         'MONGO_CRED_PSW':'fixture-only','API_TAG':'15','GIT_COMMIT':'nuevo',
         'MODELO_PATH':'/models/entrega2/sentimiento_e2_v1','STREAMING_ENABLED':'true',
         'TEST_DEPLOY_LOG':str(log),'TEST_SMOKE_RESULT':'0' if smoke_ok else '1'}
    r=subprocess.run(['/bin/bash','scripts/deploy_api.sh'],cwd=ROOT,env=env,capture_output=True,text=True)
    llamadas=[json.loads(linea) for linea in log.read_text().splitlines()]
    assert llamadas[0]=={'API_TAG':'15','MODELO_PATH':'/models/entrega2/sentimiento_e2_v1','STREAMING_ENABLED':'true'}
    if smoke_ok:
        assert r.returncode==0 and len(llamadas)==1
    else:
        assert r.returncode==1
        assert llamadas[1]=={'API_TAG':'12','MODELO_PATH':'/models/sentimiento_v1','STREAMING_ENABLED':'false'}
