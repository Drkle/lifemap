"""Muestrea /health y registra evidencia de disponibilidad, sin credenciales.

La ausencia de fallos entre muestras no garantiza disponibilidad continua.
"""
import argparse
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--url', default='https://aviation-decrease-hunger.ngrok-free.dev/health')
    p.add_argument('--horas', type=float, default=48)
    p.add_argument('--intervalo', type=float, default=300)
    p.add_argument('--salida', default='.ci-evidencias/disponibilidad.jsonl')
    a = p.parse_args()
    if a.horas < 0 or a.intervalo <= 0:
        p.error('horas debe ser >=0 e intervalo >0')
    destino = Path(a.salida)
    destino.parent.mkdir(parents=True, exist_ok=True)
    inicio = time.monotonic(); fin = inicio + a.horas * 3600
    muestras = fallos = 0
    while True:
        registro = {'fecha_utc': datetime.now(timezone.utc).isoformat(), 'url': a.url}
        try:
            req = urllib.request.Request(a.url, headers={'ngrok-skip-browser-warning': 'true'})
            t = time.monotonic()
            with urllib.request.urlopen(req, timeout=20) as r:
                datos = json.load(r)
                registro.update(http=r.status, latencia_s=round(time.monotonic()-t, 3), health=datos)
            registro['ok'] = registro['http'] == 200 and datos.get('status') == 'ok' and datos.get('commit') not in (None, 'desconocido')
        except Exception as e:
            registro.update(ok=False, error=type(e).__name__ + ': ' + str(e))
        muestras += 1
        fallos += not registro['ok']
        with destino.open('a', encoding='utf-8') as f:
            f.write(json.dumps(registro, ensure_ascii=False) + '\n')
        print(json.dumps({'muestra': muestras, 'fecha_utc': registro['fecha_utc'], 'ok': registro['ok']}), flush=True)
        restante = fin - time.monotonic()
        if restante <= 0:
            break
        time.sleep(min(a.intervalo, restante))
    print(json.dumps({'muestras': muestras, 'fallos': fallos, 'duracion_s': round(time.monotonic()-inicio, 2),
                      'nota': 'Evidencia muestreada; no prueba intervalos entre consultas.'}), flush=True)
    return 1 if fallos else 0


if __name__ == '__main__':
    raise SystemExit(main())
