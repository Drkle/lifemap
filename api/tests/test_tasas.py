import math

import pytest

from app.tasas import MIN_DIAS_NEGOCIO_DEFECTO, tasa_cierre


def test_formula_tasa_cierre_anualizada():
    # cierres / (días-negocio / 365) * 100
    assert math.isclose(tasa_cierre(3, 36500), 3.0)
    assert math.isclose(tasa_cierre(30, 109500), 10.0)  # valores de la semilla
    assert math.isclose(tasa_cierre(20, 54750), 13.333333, rel_tol=1e-6)


def test_tasa_no_es_proporcion_simple():
    # la misma proporción de cerrados (1 de 2) da tasas distintas según la exposición
    assert tasa_cierre(1, 730) != tasa_cierre(1, 7300)


def test_tasa_sin_exposicion_y_negativos():
    assert tasa_cierre(0, 0) is None
    with pytest.raises(ValueError):
        tasa_cierre(1, -5)


def test_minimo_por_defecto_es_50_anios_negocio():
    assert MIN_DIAS_NEGOCIO_DEFECTO == 18250
