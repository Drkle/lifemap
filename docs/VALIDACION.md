# Estado de validación

Esta revisión se publicó en la rama `codex/completar-lifemap`, basada en
`09eed5e`. El acceso de escritura de GitHub quedó verificado. Jenkins completó el build #8 con Yelp en el portátil del equipo y desplegó la versión 8.
Los seis endpoints se comprobaron en la URL pública. El build #10 verificó el fallo controlado y conservó la API versión 9. El equipo decidió
presentar en el mismo portátil; no hay traslado en el plan activo ni acceso remoto a Jenkins.

## Comprobado

- API: 31 pruebas aprobadas; 1 prueba de fallo intencionado omitida por defecto.
- Ingesta: 12 pruebas aprobadas, incluida recuperación tras terminar un worker real y envío acotado a dos tareas por bloque.
- Regresión adicional con MongoDB real: escritura parcial, reintentos y duplicados de origen, con agregados persistidos completos. Jenkins la ejecuta antes de la carga Yelp.
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
2. Primera entrega verificada: build #8 con Yelp (8.731 negocios y 792.133 reseñas); build #10
   FORZAR_FALLO=true con despliegue bloqueado y versión 9 conservada. Ver docs/entrega1/ y
   docs/evidencias/bloqueo_build10.json. Conservar los artefactos originales en Jenkins.
3. Mantener disponible la URL y registrar muestras durante la ventana exigida.
4. Por decisión del equipo, desarrollo y presentación seguirán en el mismo portátil. No se
   realizará traslado; la diferencia con la condición de otra máquina se documenta en el informe.
5. Abrir Power BI Desktop/servicio del equipo, crear/guardar el informe con las consultas
   suministradas y validar los permisos de mapas y actualización del tenant. No hay PBIX validado.
6. Informe E1: PDF de seis páginas preparado con evidencia real en docs/entrega1/. Actualizar
   la evidencia de disponibilidad cuando se complete el registro. El informe E2
   queda pendiente de la ejecución de esa entrega. Confirmar la fecha final con el docente.

## Límites operativos

El rollback restaura imagen, ruta de modelo y modo streaming de la API cuando falla su smoke. Ingesta, tasas y modelos usan
colecciones/volúmenes compartidos: no existe un rollback transaccional de toda la plataforma.
Las recargas deben hacerse en mantenimiento. Cambiar modelos exige una nueva revisión de
checkpoints y revisar la reproducción del topic clasificado para evitar mezclar resultados.
Power BI Import se actualiza con Actualizar; el dashboard web sí consulta automáticamente.
Los polígonos del mapa requieren tiles de OpenStreetMap, aunque Leaflet se sirve localmente.

## Preparación de la segunda entrega

Se añadió PREPARAR_ENTREGA2 para auditar Yelp y entrenar en carpetas/registros diferentes
del modelo E1, sin recrear la API ni iniciar el consumidor productivo. Los manifiestos
validan cortes, versiones y hashes de pesos. Se comprobaron seis pruebas de streaming/modelos,
el smoke positivo con 100 reseñas únicas y el rechazo real de una versión incorrecta usando
Kafka/Spark/MongoDB locales y datos sintéticos. Las pruebas API, ingesta y Spark continúan pasando. La auditoría también se ejecutó contra una cohorte MongoDB sintética.

La preparación real con Yelp y el bloqueo específico ya se ejecutaron en los builds #13 y #14,
detallados abajo. Falta la activación pública y el productor. Los cortes usados son
T=2019-01-01 y entrenamiento de riesgo al 2018-01-01.

## Evidencia real de preparación y bloqueo E2

Build #13: preparación SUCCESS con Yelp; 510.850 reseñas hasta T y 281.283 reservadas.
Sentimiento E2: regresión logística con accuracy 0,8093 y F1 macro 0,6988. Riesgo: AUC-ROC
0,5763, AUC-PR 0,0942 frente a prevalencia 0,0792 y recall 0,3176; la capacidad es limitada.
Build #14: fallo controlado de versión en el smoke, despliegue omitido y API versión 12
conservada. Los JSON revisados están en docs/evidencias; los artefactos originales en Jenkins.

Se validó además la sonda de salud con Kafka 3.9.1/MongoDB reales (tres particiones y lag cero),
el rechazo de latido vencido, la espera ante HTTP 200 degradado y dos regresiones de despliegue
que comprueban conservación/restauración de imagen, ruta de modelo y modo. Las 31 pruebas API
pasan. Falta ejecutar la activación real indicada en docs/ACTIVAR_ENTREGA2.md y revisar /health;
el productor real todavía no se ha iniciado en el portátil del equipo.
