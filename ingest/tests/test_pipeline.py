import pandas as pd

import pipeline_ingesta


def test_sumar_reportes():
    total = pipeline_ingesta._sumar(
        [{"total_inicial": 3, "R2_texto_vacio": 1, "total_final": 2}, {"total_inicial": 2, "total_final": 2}],
        ("R2_texto_vacio",),
    )
    assert total == {"total_inicial": 5, "R2_texto_vacio": 1, "total_final": 4}


def test_caja_desde_entorno(monkeypatch):
    monkeypatch.setenv("LIFEMAP_CAJA", "27.5,28.3,-82.9,-82.2")
    assert pipeline_ingesta._caja() == (27.5, 28.3, -82.9, -82.2)
    monkeypatch.setenv("LIFEMAP_CAJA", "")
    assert pipeline_ingesta._caja() is None
