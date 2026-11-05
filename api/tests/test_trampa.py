"""Prueba "trampa" para demostrar que un test fallido bloquea el despliegue.

Está desactivada por defecto. Se activa lanzando el job de Jenkins con el parámetro
FORZAR_FALLO=true. El pipeline debe quedar en rojo y la etapa de despliegue no debe
ejecutarse. Guardar la captura en docs/evidencias/ para el informe.
"""
import os

import pytest


@pytest.mark.skipif(os.getenv("FORZAR_FALLO", "false").lower() != "true",
                    reason="Solo se activa con FORZAR_FALLO=true")
def test_fallo_intencional():
    assert False, "Fallo intencional: el despliegue NO debe ejecutarse"
