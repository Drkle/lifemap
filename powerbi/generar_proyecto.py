"""Genera un PBIP editable, sin credenciales ni datos inventados.

Formato PBIR-Legacy/model.bim conforme a la estructura del ejemplo oficial:
https://github.com/microsoft/Analysis-Services/tree/master/pbidevmode/fabricps-pbip/SamplePBIP
La validación de apertura/renderizado requiere Power BI Desktop en Windows.
"""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'LifeMap'

def guardar(ruta, valor):
    p = OUT / ruta
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(valor, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

PARAMETROS = {'BaseUrl': 'http://localhost:5000', 'Latitud': '27.95',
              'Longitud': '-82.45', 'Radio': '5000', 'Categoria': 'Pizza'}
CONSULTAR = '''(Ruta as text) as list =>
let
    Datos = Json.Document(Web.Contents(BaseUrl, [RelativePath=Ruta,
        Query=[lat=Latitud, lon=Longitud, radio=Radio, limit="1000"],
        Timeout=#duration(0,0,2,0), Headers=[#"ngrok-skip-browser-warning"="true"]])),
    Filas = Datos[resultados],
    Completas = if List.Count(Filas) >= 1000 then
        error "La consulta alcanzó el límite de 1000 filas: reduzca Radio para evitar un informe truncado."
        else Filas
in Completas'''
COORDENADAS = '''(Filas as list, Campo as text) as list =>
List.Transform(Filas, (R) => Record.Combine({R,
    [longitud=Record.Field(R,Campo)[coordinates]{0},
     latitud=Record.Field(R,Campo)[coordinates]{1}]}))'''
# name, model type, M type, optional format/data category
TABLAS = {
 'Ventanas': [('geohash','string','type text'), ('inicio','dateTime','type datetime'),
              ('fin','dateTime','type datetime'), ('n','int64','Int64.Type'),
              ('pct_negativas','double','type number'), ('salto_pp','double','type number'),
              ('hotspot','boolean','type logical'), ('estado','string','type text'), ('latitud','double','type number'),
              ('longitud','double','type number')],
 'Alertas': [('_id','string','type text'), ('probabilidad','double','type number'),
             ('umbral','double','type number'), ('fecha','dateTime','type datetime'),
             ('modelo_version','string','type text')],
 'Supervivencia': [('dias','int64','Int64.Type'), ('supervivencia','double','type number'),
                   ('en_riesgo','int64','Int64.Type'), ('cierres','int64','Int64.Type'),
                   ('censuras','int64','Int64.Type')],
}

def consulta_tabla(nombre, columnas):
    if nombre == 'Supervivencia':
        origen = 'Json.Document(Web.Contents(BaseUrl, [RelativePath="survival/" & Uri.EscapeDataString(Categoria), Timeout=#duration(0,0,2,0)]))[curva]'
    elif nombre == 'Ventanas':
        origen = 'List.Transform(Coordenadas(Consultar("live/windows"), "centro"), each Record.AddField(_, "estado", if [hotspot] then "Hotspot" else "Sin salto significativo"))'
    else:
        origen = 'Consultar("alerts")'
    nombres = ', '.join('"'+c[0]+'"' for c in columnas)
    tipos = ', '.join('{"'+c[0]+'", '+c[2]+'}' for c in columnas)
    fechas = [c[0] for c in columnas if c[1] == 'dateTime']
    transformaciones = ', '.join('{"'+c+'", each if _ = null then null else DateTimeZone.RemoveZone(DateTimeZone.FromText(Text.From(_))), type datetime}' for c in fechas)
    normalizar = 'Table.TransformColumns(Seleccion, {'+transformaciones+'})' if fechas else 'Seleccion'
    return f'''let
    Filas = {origen},
    Seleccion = Table.FromRecords(Filas, {{{nombres}}}, MissingField.UseNull),
    Fechas = {normalizar},
    Tipada = Table.TransformColumnTypes(Fechas, {{{tipos}}}, "en-US")
in Tipada'''

MEDIDAS = {
 'Ventanas': [('Resenas', 'SUM(Ventanas[n])', '#,0'),
              ('Negativas ponderadas', 'DIVIDE(SUMX(Ventanas, Ventanas[n] * Ventanas[pct_negativas]), SUM(Ventanas[n])) / 100', '0.0%'),
              ('Latitud centro', 'MAX(Ventanas[latitud])', '0.00000'),
              ('Longitud centro', 'MAX(Ventanas[longitud])', '0.00000')],
 'Supervivencia': [('Probabilidad de supervivencia', 'MAX(Supervivencia[supervivencia])', '0.0%')]
}

def modelo():
    tables=[]
    for nombre, columnas in TABLAS.items():
        cols=[]
        for campo, tipo, _ in columnas:
            c=dict(name=campo, dataType=tipo, sourceColumn=campo, summarizeBy='none')
            if campo in ('latitud','longitud'):
                c['dataCategory'] = 'Latitude' if campo=='latitud' else 'Longitude'
            if campo in ('supervivencia','probabilidad','umbral'): c['formatString']='0.0%'
            if tipo=='dateTime': c['formatString']='yyyy-MM-dd'
            cols.append(c)
        t=dict(name=nombre, columns=cols, partitions=[dict(name=nombre, mode='import',
            source=dict(type='m', expression=consulta_tabla(nombre,columnas).splitlines()))])
        if nombre in MEDIDAS:
            t['measures']=[dict(name=n, expression=e, formatString=f) for n,e,f in MEDIDAS[nombre]]
        tables.append(t)
    expressions=[dict(name=n, kind='m', expression=json.dumps(v)+' meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]') for n,v in PARAMETROS.items()]
    expressions += [dict(name='Consultar',kind='m',expression=CONSULTAR.splitlines()),
                    dict(name='Coordenadas',kind='m',expression=COORDENADAS.splitlines())]
    return dict(name='LifeMap', compatibilityLevel=1567, model=dict(culture='es-ES',
        dataAccessOptions=dict(legacyRedirects=True, returnErrorValuesAsNull=True),
        defaultPowerBIDataSourceVersion='powerBI_V3', tables=tables, expressions=expressions))


def visual(nombre, tipo, tabla, roles, x, y, w, h, orden, titulo):
    selects=[]; projections={}
    for role, campos in roles.items():
        projections[role]=[]
        for campo, medida in campos:
            ref=f'{tabla}.{campo}'
            item={('Measure' if medida else 'Column'):dict(Expression=dict(SourceRef=dict(Source='t')), Property=campo), 'Name':ref, 'NativeReferenceName':campo}
            if item not in selects: selects.append(item)
            projections[role].append(dict(queryRef=ref))
    query=dict(Version=2, From=[dict(Name='t',Entity=tabla,Type=0)], Select=selects)
    if 'Category' in roles:
        query['OrderBy']=[dict(Direction=1,Expression=dict(Column=dict(Expression=dict(SourceRef=dict(Source='t')),Property=roles['Category'][0][0])))]
    pos=dict(x=x,y=y,z=orden*1000,width=w,height=h,tabOrder=orden*1000)
    title_properties = dict(show=dict(expr=dict(Literal=dict(Value='true'))),
                            text=dict(expr=dict(Literal=dict(Value="'"+titulo+"'"))))
    sv=dict(visualType=tipo,projections=projections,prototypeQuery=query,
            drillFilterOtherVisuals=True,vcObjects=dict(title=[dict(properties=title_properties)]))
    cfg=dict(name=nombre,layouts=[dict(id=0,position=pos)],singleVisual=sv)
    return dict(config=json.dumps(cfg,ensure_ascii=False),filters='[]',x=x,y=y,z=orden*1000,width=w,height=h)


def generar():
    guardar('LifeMap.pbip',dict(version='1.0',artifacts=[dict(report=dict(path='LifeMap.Report'))],settings=dict(enableAutoRecovery=True)))
    guardar('LifeMap.SemanticModel/definition.pbism',dict(version='1.0',settings=dict(qnaEnabled=False)))
    guardar('LifeMap.SemanticModel/model.bim',modelo())
    guardar('LifeMap.Report/definition.pbir',dict(version='4.0',datasetReference=dict(byPath=dict(path='../LifeMap.SemanticModel'),byConnection=None)))
    vs=[visual('mapa_celdas','map','Ventanas',{
        'Category':[('geohash',False)],'Series':[('estado',False)],'Latitude':[('Latitud centro',True)],
        'Longitude':[('Longitud centro',True)],'Size':[('Resenas',True)],
        'Tooltips':[('Negativas ponderadas',True)]},20,20,610,330,1,'Celdas y hotspots: volumen y sentimiento'),
        visual('tabla_alertas','tableEx','Alertas',{'Values':[(c,False) for c in ['_id','probabilidad','umbral','fecha','modelo_version']]},650,20,610,330,2,'Alertas activas: riesgo de cierre (proxy)'),
        visual('curva_km','lineChart','Supervivencia',{'Category':[('dias',False)],'Y':[('Probabilidad de supervivencia',True)],
            'Tooltips':[(c,False) for c in ['en_riesgo','cierres','censuras']]},20,370,610,330,3,'Supervivencia Kaplan-Meier: categoría seleccionada'),
        visual('evolucion','lineChart','Ventanas',{'Category':[('inicio',False)],'Y':[('Negativas ponderadas',True)]},650,370,610,330,4,'Evolución: reseñas negativas ponderadas')]
    guardar('LifeMap.Report/report.json',dict(config=json.dumps(dict(version='5.43',activeSectionIndex=0)),filters='[]',layoutOptimization=0,pods=[],publicCustomVisuals=[],resourcePackages=[],sections=[dict(name='ReportSectionLifeMap',displayName='LifeMap | Entrega 2',displayOption=1,filters='[]',height=720,width=1280,ordinal=0,config='{}',visualContainers=vs)]))
    print('Generado:',OUT/'LifeMap.pbip')

if __name__=='__main__': generar()
