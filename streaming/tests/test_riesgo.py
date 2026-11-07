import sys
from pathlib import Path
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'api' / 'app'))
from analitica import probabilidad


def test_json_portable_coincide_con_sklearn():
    x = np.array([[0, 3], [1, 5], [2, 7], [7, 1], [8, 2], [9, 4]], dtype=float)
    y = [0, 0, 0, 1, 1, 1]
    pipe = make_pipeline(StandardScaler(), LogisticRegression()).fit(x, y)
    scaler, lr = pipe.steps[0][1], pipe.steps[1][1]
    modelo = {'features': ['a', 'b'], 'media': scaler.mean_.tolist(), 'escala': scaler.scale_.tolist(),
        'coeficientes': lr.coef_[0].tolist(), 'intercepto': float(lr.intercept_[0])}
    for fila, esperado in zip(x, pipe.predict_proba(x)[:, 1]):
        assert abs(probabilidad(modelo, dict(zip(['a', 'b'], fila))) - esperado) < 1e-10
