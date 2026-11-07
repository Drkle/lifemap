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


def test_bloques_acotan_tareas_y_conservan_reportes(monkeypatch):
    from distributed import Client, LocalCluster
    from dask import delayed
    with LocalCluster(n_workers=2, threads_per_worker=1, processes=False, dashboard_address=None) as cluster:
        with Client(cluster) as client:
            originales = client.compute
            tamaños = []
            def observar(tareas, **kwargs):
                tamaños.append(len(tareas))
                return originales(tareas, **kwargs)
            monkeypatch.setattr(client, 'compute', observar)
            tareas = [delayed(lambda x: {'n': x})(i) for i in range(7)]
            assert pipeline_ingesta.calcular_por_bloques(client, tareas, 2) == [{'n': i} for i in range(7)]
            assert tamaños == [2, 2, 2, 1]


def test_diccionario_se_recupera_si_un_worker_muere(tmp_path):
    from distributed import Client, LocalCluster
    from dask import delayed
    marcador = str(tmp_path / 'worker_reiniciado')
    def trabajo(info):
        import os
        from pathlib import Path
        p = Path(marcador)
        if not p.exists():
            p.touch()
            os._exit(1)  # simula caída real; el grafo debe reconstruir los datos
        return len(info), info['5']['geohash']
    with LocalCluster(n_workers=2, threads_per_worker=1, processes=True, memory_limit='512MiB', dashboard_address=None) as cluster:
        with Client(cluster) as client:
            info = {str(i): {'geohash': 'dhvru7'} for i in range(100)}
            futuro = client.compute(delayed(trabajo)(info), retries=2)
            assert futuro.result(timeout=60) == (100, 'dhvru7')


def test_reporte_duplicados_globales_no_cuenta_reintentos():
    reportes = [{'total_inicial': 3, 'total_final': 3}, {'total_inicial': 2, 'total_final': 2}]
    r = pipeline_ingesta.finalizar_reporte_resenas(reportes, 3)
    assert r['R5_duplicado'] == 2 and r['total_final'] == 3


def test_reporte_rechaza_datos_ajenos_a_las_tareas():
    import pytest
    with pytest.raises(RuntimeError, match='concurrentes'):
        pipeline_ingesta.finalizar_reporte_resenas([{'total_final': 2}], 3)
