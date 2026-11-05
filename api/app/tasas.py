"""Fórmula de la tasa de cierre anualizada (la misma AFR del ejercicio de discos).

    Tasa de cierre (%) = cierres / (días-negocio / 365) * 100

Este archivo existe idéntico en api/app/tasas.py y en spark/jobs/tasas.py; ambas copias
tienen su prueba unitaria en el pipeline de Jenkins.
"""

from __future__ import annotations

DIAS_POR_ANIO = 365

# Mínimo de días-negocio para comparar la tasa de un grupo (50 años-negocio).
# Con 50 años-negocio, un cierre adicional mueve la tasa 2 puntos porcentuales; por debajo
# de eso la tasa de un grupo pequeño depende de uno o dos cierres y no es comparable.
MIN_DIAS_NEGOCIO_DEFECTO = 50 * DIAS_POR_ANIO


def tasa_cierre(cierres: int | float, dias_negocio: int | float) -> float | None:
    """Tasa de cierre anualizada en porcentaje; None si no hay exposición."""

    if cierres < 0 or dias_negocio < 0:
        raise ValueError("cierres y dias_negocio no pueden ser negativos")
    if dias_negocio == 0:
        return None
    return cierres / (dias_negocio / DIAS_POR_ANIO) * 100
