# Primera ejecución de la segunda entrega

Esta fase se hace en el mismo portátil. No requiere cambiar ngrok ni borrar la ingesta de Yelp.
La fase de preparación no recrea la API ni arranca el consumidor de producción. Sí construye
la imagen cliente, ejecuta trabajos offline en Spark y levanta Kafka para la prueba aislada.

## Ejecutar en Jenkins

Después de incorporar esta revisión, esperar a que no haya otros builds ejecutándose.
Si los parámetros nuevos aún no aparecen, dejar terminar el build normal de actualización.

| Parámetro | Valor para preparar |
|---|---|
| FECHA_CORTE | 2019-01-01 |
| CORTE_ENTRENAMIENTO | 2018-01-01 |
| PREPARAR_ENTREGA2 | true |
| VERIFICAR_KAGGLE | true |
| ENTREGA2 | false |
| FORZAR_FALLO | false |
| FORZAR_FALLO_STREAMING | false |
| FORCE_RELOAD | false |
| ENTRENAR_MODELO / ENTRENAR_RIESGO | false; se entrena si faltan candidatos válidos |
| RECALCULAR_TASAS / EJECUTAR_BALANCEO | false |

El pipeline reutiliza la ingesta completa, las tasas y el balanceo existentes. La primera
preparación puede tardar por la construcción de la imagen y los entrenamientos con datos reales.
No iniciar otro build mientras esté ejecutándose.

## Qué comprueba y dónde guarda la evidencia

1. Auditoría de solo lectura sobre MongoDB: reseñas hasta T y posteriores a T, presencia de
   las tres clases de sentimiento, horizonte temporal completo y clases de riesgo en
   entrenamiento/validación/prueba con negocios disjuntos. Si un corte no sirve, falla con
   los conteos; no ajusta fechas silenciosamente para conseguir mejores métricas.
2. Conserva `/models/sentimiento_v1` y su registro `sentimiento_v1` de E1. Entrena el candidato
   en `/models/entrega2/sentimiento_e2_v1`, registrando métricas bajo `sentimiento_e2_v1`.
3. Entrena riesgo en `/models/entrega2/riesgo_v1.json`, sin publicar puntuaciones iniciales
   en risk_scores. Evalúa con periodo posterior y negocios diferentes; escoge el umbral
   con validación del periodo de entrenamiento, no con la prueba.
4. Genera manifiesto con ambos cortes, versiones y SHA-256 de archivos/pesos, y valida que
   los modelos no cambiaron después de la prueba. Un JSON de metadata por sí solo no basta.
5. Crea base, topics y checkpoints exclusivos de CI, clasifica 100 reseñas, las reenvía,
   verifica riesgo/alertas, y avanza el watermark para comprobar una ventana de 100 únicas.
6. Compara la metadata E1 antes/después y omite el despliegue de API en modo preparación.

Los artefactos están en **Build → Artifacts → .ci-evidencias/entrega2-N/** (N es el número del build):

- auditoria.json: cantidades antes/después de T y clases por cohorte.
- sentimiento_metricas.json: NB/LR y matriz de confusión con datos anteriores a T.
- riesgo_metricas.json: AUC-ROC, AUC-PR, prevalencia base, recall y umbral.
- manifest.json: rutas, versiones, hashes y revisión conjunta.
- smoke.log: resultado de la prueba del flujo.
- modelo_e1_antes.json / modelo_e1_despues.json: preservación de la metadata histórica.

Un SUCCESS de preparación significa candidatos y prueba aprobados; no que el streaming real
esté publicando reseñas o que el dashboard Power BI esté terminado. Las métricas de pruebas
sintéticas usadas en desarrollo no se presentan como resultados de Yelp.

## Después de revisar los resultados reales

Activar **ENTREGA2=true** con **PREPARAR_ENTREGA2=false** para desplegar. El consumidor valida
el manifiesto, utiliza checkpoints y topic clasificado separados por revisión de modelos,
y la API cambia al modelo preparado después de las pruebas. Se mantienen los seis endpoints
anteriores. Un build SCM posterior detecta E2 ya activa y no vuelve a E1 por el valor por defecto.

Para cambiar cortes o reentrenar modelos ya activos hace falta otra revisión de directorios;
el script rechaza sobrescribirlos. No borrar checkpoints para forzar que arranque.

La activación no inicia todavía el productor de reseñas de Yelp: ese será el siguiente paso
para controlar velocidad y observar las ventanas. Power BI y las curvas/comparaciones reales
siguen pendientes hasta tener datos/evidencia del flujo.

## Prueba negativa específica del streaming

Después de una preparación exitosa, repetir con PREPARAR_ENTREGA2=true y
FORZAR_FALLO_STREAMING=true, manteniendo FORZAR_FALLO=false. La prueba exige deliberadamente
una versión incorrecta del modelo y debe fallar al recibir las predicciones. Jenkins omite
el despliegue y compara la identidad de la API antes/después. Esta prueba es distinta del
fallo intencional de la API que ya se demostró en el build #10.

Desactivar FORZAR_FALLO_STREAMING en las ejecuciones normales.
