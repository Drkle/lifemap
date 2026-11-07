"""Verifica contratos y referencias; no sustituye apertura en Desktop."""
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_generacion_y_referencias(tmp_path):
    spec=importlib.util.spec_from_file_location('generar_pbi',ROOT/'generar_proyecto.py')
    g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
    g.OUT=tmp_path;g.generar()
    for path in (ROOT/'LifeMap').rglob('*'):
        if path.is_file() and path.suffix in ('.json','.bim','.pbip','.pbir','.pbism'):
            assert (tmp_path/path.relative_to(ROOT/'LifeMap')).read_bytes()==path.read_bytes()
    report=json.loads((tmp_path/'LifeMap.Report/report.json').read_text())
    model=json.loads((tmp_path/'LifeMap.SemanticModel/model.bim').read_text())['model']
    tables={t['name']:t for t in model['tables']}
    visuals=report['sections'][0]['visualContainers']
    assert len(visuals)==4
    assert {json.loads(v['config'])['singleVisual']['visualType'] for v in visuals}=={'map','tableEx','lineChart'}
    for v in visuals:
        sv=json.loads(v['config'])['singleVisual'];q=sv['prototypeQuery']
        entity=q['From'][0]['Entity'];table=tables[entity]
        refs=set()
        for sel in q['Select']:
            kind='Measure' if 'Measure' in sel else 'Column'
            names={r['name'] for r in table['measures' if kind=='Measure' else 'columns']}
            assert sel[kind]['Property'] in names
            refs.add(sel['Name'])
        for items in sv['projections'].values():
            assert all(item['queryRef'] in refs for item in items)
    expressions={e['name']:e['expression'] for e in model['expressions']}
    assert 'List.Count(Filas) >= 1000' in '\n'.join(expressions['Consultar'])
    assert 'localhost:5000' in expressions['BaseUrl']
    measures={m['name']:m['expression'] for m in tables['Ventanas']['measures']}
    assert 'SUMX' in measures['Negativas ponderadas'] and '/ 100' in measures['Negativas ponderadas']


def test_temas_registrados_y_recursos_presentes():
    carpeta=ROOT/'LifeMap/LifeMap.Report'
    report=json.loads((carpeta/'report.json').read_text())
    config=json.loads(report['config'])
    themes=config['themeCollection']
    packages={p['resourcePackage']['type']:p['resourcePackage'] for p in report['resourcePackages']}
    for key in ('baseTheme','customTheme'):
        theme=themes[key]
        package=packages[theme['type']]
        items=[i for i in package['items'] if i['name']==theme['name']]
        assert len(items)==1
        recurso=carpeta/'StaticResources'/package['name']/items[0]['path']
        content=json.loads(recurso.read_text())
        assert content['name']
    assert report['theme']==themes['customTheme']['name']
