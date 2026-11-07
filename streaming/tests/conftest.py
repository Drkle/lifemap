import sys
from pathlib import Path
root=Path(__file__).resolve().parents[2]
# En Docker analitica.py y el resto de módulos están en /opt/streaming.
sys.path[:0]=[str(root/'streaming'),str(root/'api'/'app')]
