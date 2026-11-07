def root = new File(args ? args[0] : '.')
def modo = new GroovyShell().evaluate(new File(root, 'jenkins/modo.groovy'))
def e1 = modo.resolver([:], false)
assert e1.ejecutar == 'false' && e1.nombre == 'E1'
assert e1.modelo == '/models/sentimiento_v1' && e1.manifest == ''
def e2 = modo.resolver([ENTREGA2: true], false)
assert e2.ejecutar == 'true' && e2.nombre == 'ACTIVAR_E2'
assert e2.modelo == '/models/entrega2/sentimiento_e2_v1'
assert e2.manifest == '/models/entrega2/manifest.json'
assert modo.resolver([ENTREGA2: false], true).ejecutar == 'true'
assert modo.resolver([PREPARAR_ENTREGA2: true], false).nombre == 'PREPARAR_E2'
assert modo.resolver([PREPARAR_ENTREGA2: true], true).ejecutar == 'false'
assert modo.resolver([PREPARAR_ENTREGA2: true, FORZAR_FALLO_STREAMING: true], false).ejecutar == 'false'
for (caso in [[ENTREGA2:true, PREPARAR_ENTREGA2:true],
              [FORZAR_FALLO:true, FORZAR_FALLO_STREAMING:true],
              [FORZAR_FALLO_STREAMING:true]]) {
    boolean rechazo = false
    try { modo.resolver(caso, false) } catch (IllegalArgumentException e) { rechazo = true }
    assert rechazo : "No se rechazó el modo ambiguo: ${caso}"
}
println('Modos Jenkins: activación manual, persistencia SCM, preparación y rechazos correctos.')
