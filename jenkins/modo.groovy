// Lógica pura: permite probar los modos sin arrancar Jenkins o Docker.
def resolver(Map parametros, boolean activa) {
    boolean preparar = parametros.PREPARAR_ENTREGA2 == true
    boolean solicitada = parametros.ENTREGA2 == true
    boolean falloApi = parametros.FORZAR_FALLO == true
    boolean falloStreaming = parametros.FORZAR_FALLO_STREAMING == true
    if (preparar && solicitada) {
        throw new IllegalArgumentException('Seleccionar PREPARAR_ENTREGA2 o ENTREGA2, no ambos.')
    }
    if (falloApi && falloStreaming) {
        throw new IllegalArgumentException('Probar un fallo controlado a la vez.')
    }
    boolean ejecutar = solicitada || (activa && !preparar)
    if (falloStreaming && !preparar && !ejecutar) {
        throw new IllegalArgumentException('FORZAR_FALLO_STREAMING requiere PREPARAR_ENTREGA2 o ENTREGA2.')
    }
    return [ejecutar: ejecutar ? 'true' : 'false',
            nombre: preparar ? 'PREPARAR_E2' : (ejecutar ? 'ACTIVAR_E2' : 'E1'),
            modelo: ejecutar ? '/models/entrega2/sentimiento_e2_v1' : '/models/sentimiento_v1',
            manifest: ejecutar ? '/models/entrega2/manifest.json' : '']
}
return this
