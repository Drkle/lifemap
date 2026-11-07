# Dashboard Power BI

`LifeMap.pq` es un documento M con consultas compartidas. En Power BI Desktop, crear
consultas en blanco con los nombres BaseUrl, Latitud, Longitud, Radio, Categoria,
Consultar, Coordenadas, Hotspots, Alertas, Ventanas, Riesgo y Supervivencia. Pegar en
el editor avanzado la expresión a la derecha de cada `shared Nombre =`, sin el
punto y coma final. Las funciones Consultar y Coordenadas se crean como funciones.
No pegar `section LifeMap` dentro de una sola consulta del Desktop.

Elegir credenciales Web **Anónimo** para la URL pública de esta API. No introducir las
credenciales de MongoDB ni Kaggle en el dashboard. Ajustar categoría y ubicación a las
que sí tengan datos en la ingesta del equipo. Un conjunto vacío no significa cero cierres.

Página de informe, cuatro visualizaciones:

1. **Mapa:** tabla Hotspots, latitud y longitud con categoría de datos Latitud/Longitud;
   tamaño por n y color por pct_negativas. Usar mapa estándar, Azure Maps si está habilitado
   en el tenant, o Shape Map con geometrías externas; el mapa estándar muestra centros.
2. **Tabla de alertas:** Alertas._id, probabilidad, fecha, modelo_version y umbral.
   Formatear probabilidad y umbral como porcentaje.
3. **Curva Kaplan-Meier:** eje X Supervivencia.dias; eje Y supervivencia, escala [0,1].
   Añadir en_riesgo, cierres y censuras al tooltip. No usar suma de probabilidades.
4. **Evolución:** Ventanas.inicio como fecha; pct_negativas como valor y geohash como leyenda.
   Para un total ponderado, usar SUMX(Ventanas, Ventanas[n] * Ventanas[pct_negativas]) / SUM(Ventanas[n]).

Las consultas Web importadas se actualizan con **Actualizar** durante la demo. Power BI
Desktop en modo Import no hace polling automático cada pocos segundos. La actualización
programada del servicio depende del plan y no ofrece ese comportamiento. Si el docente
exige automatismo sin intervención, configurar un mecanismo de ingesta a un dataset del
servicio con los permisos del tenant y probarlo allí; no afirmar que Import es streaming.
El dashboard web `/dashboard` sí consulta la API automáticamente cada 15 segundos.

Guardar el PBIX desde Desktop y publicar según la cuenta de la universidad. Esta parte
requiere Power BI Desktop/servicio y acceso al tenant; el repositorio no contiene un PBIX
supuestamente validado ni credenciales de publicación.
