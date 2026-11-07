# Informe de la primera entrega

**Integrantes:** Juan Echeverrri y Sebastian Botero, escritos según los nombres proporcionados por el equipo.

- [Informe PDF de seis páginas](informe_e1.pdf).
- [Versión HTML editable/imprimible](informe_e1.html).
- [Generador del informe](generar_informe.py), solo biblioteca estándar de Python.
- [Resultados extraídos del build #8](../evidencias/build8_resultados.json).
- [Comprobación puntual de los seis endpoints públicos](../evidencias/api_publica_build8.json).

El informe incorpora resultados reales y señala tres evidencias aún pendientes: el fallo
controlado en Jenkins, el servidor separado y la ventana de disponibilidad. No sustituir
esos pendientes por afirmaciones de cumplimiento antes de ejecutarlos. Reemitir la página 6
cuando existan resultados verificables; actualizar también los JSON de evidencia.

## Prueba controlada en Jenkins

El pipeline ya captura commit, versión e imagen de la API antes y después de un build
FORZAR_FALLO=true, y archiva el resultado en los artefactos del propio build.

1. Esperar a que no haya otro build ejecutándose y que /health muestre una versión válida.
2. En `lifemap-main` → Build with Parameters: activar **FORZAR_FALLO**, dejar **ENTREGA2**,
   **FORCE_RELOAD**, **ENTRENAR_MODELO**, **ENTRENAR_RIESGO**, **RECALCULAR_TASAS** y
   **EJECUTAR_BALANCEO** desactivados. Puede mantenerse VERIFICAR_KAGGLE marcado: la falla
   ocurre antes de esa etapa.
3. Ejecutar una sola vez. El resultado esperado es **FAILURE** en la prueba intencional y
   las etapas posteriores omitidas. La consola debe indicar `[bloqueo] OK`.
4. En los artefactos del build, abrir `.ci-evidencias/bloqueo-N/resultado.json`. Debe tener
   commit_conservado, version_conservada e imagen_conservada en true. Conservar captura del
   historial y de las etapas, y el enlace al build. No dejar FORZAR_FALLO activo en siguientes builds.

Un build rojo por otro error no demuestra esta prueba. La comparación de identidad comprueba
conservación de la API, no rollback transaccional de datos/modelos.

Este entorno no tiene acceso al `localhost:8080` del portátil ni credenciales Jenkins. Por eso
la ejecución del build controlado debe iniciarla el equipo desde su sesión, o proporcionar
una conexión autenticada accesible sin enviar secretos por chat.

## Servidor y disponibilidad

La sección 6 del Word exige otra máquina. Un equipo del laboratorio satisface esa condición;
no es obligatorio pagar nube. Seguir [la guía del servidor](../../deploy/SERVIDOR.md).
La API pública debe seguir funcionando al apagar el portátil tras mover el túnel.

Después de validar el servidor, registrar muestras durante 48 horas o más:

```bash
python3 scripts/monitorear_disponibilidad.py --horas 48 --intervalo 300
```

El registro queda en `.ci-evidencias/disponibilidad.jsonl`. El monitor muestra la evolución de
cada muestra y el resumen de fallos; no demuestra continuidad entre muestras. El proceso y
el servidor deben permanecer en ejecución durante la ventana y la sustentación.

## Regenerar y exportar

```bash
python3 docs/entrega1/generar_informe.py
```

Abrir el HTML e imprimir a PDF: A4, escala 100 %, sin encabezados/pies del navegador, con fondos.
Comprobar que el resultado tenga **seis páginas** y que ninguna tabla esté recortada. El PDF
publicado se revisó con Chromium y pdfinfo. No instalar dependencias de renderizado en los
contenedores de producción solo para imprimir el informe.
