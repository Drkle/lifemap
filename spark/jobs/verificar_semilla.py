"""Verifica las tasas calculadas sobre la semilla contra valores conocidos.

Se ejecuta en cada build después de tasas_mapreduce.py --negocios negocios_semilla.
Si un cambio rompe el MapReduce o la fórmula, este job falla y Jenkins no despliega.
"""
import math
import sys

from comun import crear_sesion, leer

ESPERADO_CATEGORIA = {
    "Pizza": {"cierres": 20, "dias_negocio": 54750, "negocios": 50, "tasa_cierre": 13.3333},
    "Mexican": {"cierres": 10, "dias_negocio": 54750, "negocios": 50, "tasa_cierre": 6.6667},
}


def main():
    spark = crear_sesion("lifemap-verificar-semilla")
    errores = []
    categorias = {r["categoria"]: r.asDict() for r in leer(spark, "semilla_tasas_categoria").collect()}
    for cat, esperado in ESPERADO_CATEGORIA.items():
        real = categorias.get(cat)
        if real is None:
            errores.append(f"falta la categoría {cat}")
            continue
        for campo, valor in esperado.items():
            if not math.isclose(real[campo], valor, abs_tol=1e-3):
                errores.append(f"{cat}.{campo}: esperado {valor}, obtenido {real[campo]}")

    celdas = [r.asDict(recursive=True) for r in leer(spark, "semilla_tasas_celda").collect()]
    sumas = {c: sum(x[c] for x in celdas) for c in ("cierres", "dias_negocio", "negocios", "n_resenas", "negativas")}
    for campo, valor in {"cierres": 30, "dias_negocio": 109500, "negocios": 100,
                         "n_resenas": 400, "negativas": 150}.items():
        if sumas[campo] != valor:
            errores.append(f"suma de celdas {campo}: esperado {valor}, obtenido {sumas[campo]}")
    if any(c["geometry"]["type"] != "Polygon" for c in celdas):
        errores.append("alguna celda no tiene geometría Polygon")

    meta = leer(spark, "semilla_tasas_meta").collect()[0].asDict()
    if not math.isclose(meta["tasa_global"], 10.0, abs_tol=1e-3):
        errores.append(f"tasa global: esperado 10.0, obtenido {meta['tasa_global']}")

    spark.stop()
    if errores:
        print("[verificar] FALLO:\n  - " + "\n  - ".join(errores))
        return 1
    print(f"[verificar] OK: Pizza 13,333 %, Mexican 6,667 %, global 10 %, {len(celdas)} celdas "
          f"con sumas 30/109500/100/400/150")
    return 0


if __name__ == "__main__":
    sys.exit(main())
