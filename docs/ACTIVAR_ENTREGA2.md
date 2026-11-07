# Activar la segunda entrega después de las pruebas aprobadas

## Evidencia disponible

- Build #13: SUCCESS en PREPARAR_ENTREGA2. Separó 510.850 reseñas históricas y reservó
  281.283 para streaming; entrenó candidatos y aprobó el smoke de 100 reseñas únicas.
- Build #14: FAILURE intencional al exigir una versión incorrecta en el smoke. El despliegue
  quedó omitido y `[bloqueo] OK` confirmó conservación de `lifemap-api:12`.
- Evidencia revisada en `docs/evidencias/preparacion_build13.json` y
  `docs/evidencias/bloqueo_streaming_build14.json`. Conservar los artefactos originales Jenkins.

El modelo de riesgo ofrece señal limitada: AUC-ROC 0,5763; AUC-PR 0,0942 frente a prevalencia
0,0792; recall 0,3176 en el umbral 0,5656 elegido en validación. No se presenta como un
predictor confiable de cierre real: la etiqueta es un proxy y muchos cierres no se detectan.
La preparación ya se hizo con Yelp; no hace falta forzar descarga ni entrenamiento de nuevo.

## Una ejecución de activación en Jenkins

Esperar a que no haya otro build activo. Mantener las fechas y ejecutar:

| Parámetro | Valor |
|---|---|
| FECHA_CORTE | 2019-01-01 |
| CORTE_ENTRENAMIENTO | 2018-01-01 |
| ENTREGA2 | true |
| VERIFICAR_KAGGLE | true |
| PREPARAR_ENTREGA2 | false |
| FORZAR_FALLO | false |
| FORZAR_FALLO_STREAMING | false |
| Todas las demás casillas | false |

El pipeline reutiliza los candidatos existentes, vuelve a verificar versiones y smoke,
prepara índices E2, crea un topic clasificado por revisión, arranca el consumidor y despliega
la API con el modelo temporal. No arranca el productor real de Yelp.

## Resultado esperado

- SUCCESS, con `[smoke] E2: Kafka/consumidor y los cuatro endpoints nuevos OK`.
- `/health`: versión/commit del nuevo build, Kafka ok, tres particiones, consumidor_activo=true
  y retraso_mensajes presente. Sin productor, un retraso de cero es normal.
- La sonda usa latido para saber si el consumidor vive. El último lote puede ser antiguo
  cuando no llegan mensajes; el tiempo desde ese progreso se informa por separado.
- Las consultas de alertas, riesgo y hotspots pueden devolver listas vacías antes de
  reproducir las reseñas. Supervivencia sí consulta los negocios históricos.

La prueba de salud espera estado ok, no solo HTTP 200: la API responde 200 degradado mientras
inicia el consumidor. Si la verificación de despliegue falla, el script restaura la imagen,
ruta del modelo y modo streaming de la API anterior. No revierte los datos ni garantiza
rollback completo del consumidor; no iniciar el productor si el despliegue falló.

## Después del SUCCESS

Comprobar la URL pública y el modelo cargado antes de publicar reseñas. El siguiente paso es
iniciar el productor con límite/velocidad controlados y observar lag, ventanas, hotspots y
alertas. Power BI, comparaciones de supervivencia por zona y el informe final siguen pendientes.
El dashboard web no sustituye el archivo Power BI solicitado por el trabajo.
