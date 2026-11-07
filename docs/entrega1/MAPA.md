# Vista visual para sustentar la primera entrega

Abrir **http://localhost:5000/dashboard/entrega1** después del despliegue del build
que incorpora esta ruta. La URL pública admite el mismo sufijo `/dashboard/entrega1`.
La ruta `/dashboard` mantiene la vista de streaming de la segunda entrega.

La nueva vista solo necesita los datos históricos, las tasas y la API de E1; no
consulta endpoints de Kafka ni de streaming. La prueba de sentimiento usa el modelo
actual de la API y muestra su versión: si está activa E2, puede ser su modelo temporal,
no el del experimento E1. Para comparar NB/LR usar las métricas históricas del informe E1.

## Demostración de tres minutos

1. Mantener Tampa (27.95, -82.45) y radio 2000 metros; pulsar Consultar radio.
2. Explicar colores: abiertos al corte y clasificados como cerrados. Pulsar un punto
   para ver categoría, estrellas, número de reseñas y porcentaje negativo.
3. Mostrar la tabla y los indicadores del radio: cantidad de negocios, cierres,
   exposición, tasa anualizada, estrellas y negativas ponderadas por reseñas.
4. Pulsar Seleccionar rectángulo y hacer clic en dos esquinas opuestas del mapa.
   La selección llama POST /businesses/within; cambia puntos y lista. El resumen de la
   derecha sigue siendo del radio, según la nota visible. No atribuirlo al rectángulo.
5. Pulsar Volver al radio. Mostrar tasas por categoría y exposición. Esa tabla es
   global para la población seleccionada de Florida, independiente del área y categoría
   elegidas en el formulario. Muestra las primeras 15 categorías elegibles por tasa.
6. Probar una reseña y explicar probabilidades y versión del modelo.

El mapa lista como máximo 1000 negocios y avisa si alcanza el límite. El resumen del
radio se calcula en MongoDB sobre todos los negocios del área, sin limitarse a los
marcadores. No confundir los límites de la lista con el total de la zona.

El mínimo de exposición inicial es 36.500 días-negocio (100 años-negocio), configurable;
no garantiza significancia estadística. La tasa es eventos por 100 años-negocio, no una
probabilidad futura de cierre. Las fechas se aproximan con reseñas y el estado final.

Leaflet se sirve localmente. El fondo usa OpenStreetMap y requiere conexión externa;
si falla, se avisa y las geometrías siguen disponibles. No se incorporan credenciales.
