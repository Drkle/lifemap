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


def test_scatter_diccionario_como_objeto_unico():
    """Regresión del grafo de miles de futuros que derribaba el scheduler."""
    from distributed import Client, LocalCluster
    from dask import delayed
    with LocalCluster(n_workers=2, threads_per_worker=1, processes=False, dashboard_address=None) as cluster:
        with Client(cluster) as client:
            info = {str(i): {'geohash': 'dhvru7'} for i in range(100)}
            futuro = client.scatter([info], broadcast=True)[0]
            resultado = client.compute(delayed(lambda valor: (len(valor), valor['5']['geohash']))(futuro)).result()
            assert resultado == (100, 'dhvru7')
            assert len(client.who_has()) == 2  # un objeto compartido y una tarea, no 100 objetos


def test_reporte_duplicados_globales_no_cuenta_reintentos():
    reportes = [{'total_inicial': 3, 'total_final': 3}, {'total_inicial': 2, 'total_final': 2}]
    r = pipeline_ingesta.finalizar_reporte_resenas(reportes, 3)
    assert r['R5_duplicado'] == 2 and r['total_final'] == 3


def test_reporte_rechaza_datos_ajenos_a_las_tareas():
    import pytest
    with pytest.raises(RuntimeError, match='concurrentes'):
        pipeline_ingesta.finalizar_reporte_resenas([{'total_final': 2}], 3)
