# Estado de validación

Esta revisión se publicó en la rama `codex/completar-lifemap`, basada en
`09eed5e`. El acceso de escritura de GitHub quedó verificado. Todavía no se ha
desplegado en el servidor del equipo ni se ha proporcionado una URL de Jenkins accesible
desde este entorno. Las comprobaciones locales no sustituyen ese build.

## Comprobado

- API: 30 pruebas aprobadas; 1 prueba de fallo intencionado omitida por defecto.
- Ingesta: 9 pruebas aprobadas, incluida ejecución real de `scatter` con dos workers Dask.
- Spark: 9 pruebas aprobadas, incluyendo entrenamiento/predicción y equivalencia RDD/groupBy.
- Modelo portable de riesgo: igualdad numérica entre la probabilidad JSON y scikit-learn.
- Entrenamiento de riesgo completo con MongoDB y cohorte sintética: separación por negocio,
  validación y evaluación temporal; el JSON se genera. Las métricas sintéticas no son evidencia Yelp.
- Kafka 3.9.1 en KRaft, Spark 3.5.3 y MongoDB 7: prueba de flujo real con 100 reseñas únicas,
  reenvío de las mismas 100, predicciones/probabilidades con versión esperada, actualización de
  riesgo y alerta, y una reseña de control para avanzar el watermark. Ventana final: n=100,
  50 % negativas, sin duplicar el reenvío.
- Dashboard en Chromium: consultas HTTP reales a MongoDB de prueba, tabla de alertas,
  ambas curvas SVG, ausencia de errores JavaScript y vista móvil de 390 px sin desbordamiento.
- Imagen Docker de streaming: construcción final completada con Python 3.11 y Java 17.
- Predictor real de API: carga de PipelineModel y predicción del fixture verificadas.
- Sintaxis Python, shell, Groovy del Jenkinsfile y configuración Compose con perfil streaming.

La comprobación Groovy solo valida sintaxis: no sustituye una ejecución del pipeline en Jenkins.

## Pendiente de servicios externos y datos del equipo

1. Revisar e integrar la propuesta de cambios de `codex/completar-lifemap`.
2. Ejecutar Jenkins con las credenciales del equipo y verificar la descarga/ingesta de Yelp,
   métricas reales, balanceo y modelo guardado. El dataset completo de reseñas mide 5,34 GB;
   este entorno tiene un disco total de unos 8 GB y no se usó para fingir esa ejecución.
3. Demostrar build verde, build `FORZAR_FALLO=true`, webhook/polling y hash real en `/health`.
4. Desplegar en una VM o equipo de laboratorio, distinto del portátil, con URL pública y la
   ventana de disponibilidad requerida. No se aprovisionó una VM con costes o cuenta desconocidos.
5. Abrir Power BI Desktop/servicio del equipo, crear/guardar el informe con las consultas
   suministradas y validar los permisos de mapas y actualización del tenant. No hay PBIX validado.
6. Exportar evidencia real mediante `informe.py`, interpretar resultados y ajustar los informes
   a 6/10 páginas. Acordar la fecha final con el docente por la discrepancia de los documentos.

## Límites operativos

El rollback restaura la imagen API cuando falla su smoke. Ingesta, tasas y modelos usan
colecciones/volúmenes compartidos: no existe un rollback transaccional de toda la plataforma.
Las recargas deben hacerse en mantenimiento. Cambiar modelos exige una nueva revisión de
checkpoints y revisar la reproducción del topic clasificado para evitar mezclar resultados.
Power BI Import se actualiza con Actualizar; el dashboard web sí consulta automáticamente.
Los polígonos del mapa requieren tiles de OpenStreetMap, aunque Leaflet se sirve localmente.
