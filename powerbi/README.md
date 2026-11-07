# Power BI de LifeMap

El informe ya está configurado en **`LifeMap/LifeMap.pbip`**. Incluye modelo Import,
consultas Power Query y cuatro visualizaciones vinculadas a las columnas/medidas:

1. Mapa de celdas: tamaño por reseñas, leyenda hotspot/sin salto significativo y
   tooltip de negativas ponderadas. Las coordenadas son centros de geohash.
2. Tabla de alertas activas: negocio, riesgo, umbral, fecha y versión del modelo.
3. Curva Kaplan-Meier: días y supervivencia, con población en riesgo/cierres/censuras.
4. Evolución temporal: negativas ponderadas por número de reseñas (no media de porcentajes).

## Abrir en el portátil

1. Actualizar el repositorio: `git pull --ff-only origin main`.
2. Abrir `powerbi/LifeMap/LifeMap.pbip` en Power BI Desktop actualizado. Si no reconoce
   PBIP, habilitar **Archivo > Opciones y configuración > Opciones > Características de
   versión preliminar > Opción para guardar proyectos Power BI (.pbip)** y reiniciar.
   El nombre puede variar por versión.
3. Pulsar **Actualizar**. Elegir autenticación **Anónimo** para `http://localhost:5000`.
   Mantener Docker y la API ejecutándose. No introducir credenciales MongoDB/Kaggle.
4. Si el mapa está deshabilitado, habilitar los elementos visuales de mapa en las
   opciones de seguridad (y en el tenant si la universidad los restringe).
5. Guardar una copia **LifeMap.pbix** mediante **Archivo > Guardar como**.

No hay que crear tablas ni arrastrar campos manualmente. El PBIP no contiene datos
precargados: antes de la primera actualización los visuales estarán vacíos.

## Parámetros y alcance

**Transformar datos > Editar parámetros** permite ajustar BaseUrl, Latitud, Longitud,
Radio y Categoria. Valores iniciales: API local, Tampa (27.95, -82.45), radio 5000 m,
Pizza. Esta ubicación no representa todos los negocios de Florida.

La API espacial limita cada consulta a 1000 filas; si se alcanza ese número, Power
Query da un error explícito. Reducir Radio antes de interpretar cifras. No se muestran
resultados truncados como totales globales. No aumentar el radio para obtener un total.
La curva de supervivencia usa **toda la categoría**, no el radio del mapa; los controles
espaciales solo afectan mapa, evolución y alertas. Categoría principal y fechas proceden
de las reseñas: la supervivencia y el riesgo son estimaciones proxy.

Un hotspot vacío es un resultado posible. El mapa también muestra celdas sin hotspot,
con leyenda, para distinguir ausencia de salto y ausencia de datos. El riesgo se presenta
como puntuación de un modelo con capacidad limitada, no como certeza de cierre.

`pct_negativas` llega en escala 0–100. La medida DAX pondera por n y divide entre 100
antes del formato porcentaje. La curva KM y el riesgo ya llegan en escala 0–1. No se
suman probabilidades. Las tablas se mantienen independientes para no unir ventanas con
negocios y multiplicar registros.

## Actualización y estado de validación

**Actualizar** vuelve a consultar la API. Import en Desktop no hace polling automático.
La actualización automática en el servicio depende de una cuenta/tenant, gateway para
localhost y permisos de publicación; sigue pendiente configurar y demostrar ese requisito.
El dashboard web `/dashboard` sí consulta automáticamente, pero no sustituye Power BI.

Se validan generación reproducible, referencias de visuales/medidas/columnas, estructura
JSON y contratos de la API. **Aún se requiere comprobar apertura, carga y renderizado
con Power BI Desktop en Windows**; este entorno Linux no ejecuta Power BI. El archivo
no se presenta como un PBIX ya validado ni como evidencia de actualización automática.

Para regenerar: `python powerbi/generar_proyecto.py`. Las pruebas están en
`powerbi/tests/test_proyecto.py`. El antiguo `LifeMap.pq` se conserva como alternativa
manual; no se necesita para abrir el nuevo PBIP.

Referencia del formato: ejemplo oficial Microsoft Analysis-Services,
`pbidevmode/fabricps-pbip/SamplePBIP` (PBIR-Legacy y modelo BIM). El generador es propio;
no incluye recursos, datos ni visualizaciones copiadas del informe de ejemplo.
