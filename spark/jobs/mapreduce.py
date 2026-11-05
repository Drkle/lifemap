"""MapReduce de cierres y días-negocio con RDD, validado contra groupBy de DataFrames.

Es el mismo patrón de la Parte A del ejercicio de discos: allí cada fila era un disco-día
y se emitía (modelo, (1, falla)); aquí cada fila es un negocio que ya trae sus
días-negocio, así que se emite (clave, (cierre, días_negocio, 1)).
"""

from __future__ import annotations

from pyspark.sql import functions as F

from tasas import tasa_cierre


def mapreduce_cierres(df, clave: str):
    """RDD: (clave, (cierre, días_negocio, 1)) -> reduceByKey -> DataFrame."""
    pares = df.select(clave, "evento", "dias_negocio").rdd.map(
        lambda fila: (fila[0], (int(fila[1]), int(fila[2]), 1))
    )
    reducido = pares.reduceByKey(lambda a, b: (a[0] + b[0], a[1] + b[1], a[2] + b[2]))
    filas = reducido.map(lambda kv: (kv[0], kv[1][0], kv[1][1], kv[1][2]))
    return df.sparkSession.createDataFrame(
        filas, f"{clave} string, cierres long, dias_negocio long, negocios long"
    )


def groupby_cierres(df, clave: str):
    return df.groupBy(clave).agg(
        F.sum("evento").cast("long").alias("cierres"),
        F.sum("dias_negocio").cast("long").alias("dias_negocio"),
        F.count("*").cast("long").alias("negocios"),
    )


def mapreduce_negativas(df, clave: str):
    """RDD: (clave, (negativa, 1)) -> reduceByKey: reseñas y negativas por clave."""
    pares = df.select(clave, "negativa").rdd.map(lambda fila: (fila[0], (int(fila[1]), 1)))
    reducido = pares.reduceByKey(lambda a, b: (a[0] + b[0], a[1] + b[1]))
    filas = reducido.map(lambda kv: (kv[0], kv[1][0], kv[1][1]))
    return df.sparkSession.createDataFrame(filas, f"{clave} string, negativas long, n_resenas long")


def groupby_negativas(df, clave: str):
    return df.groupBy(clave).agg(
        F.sum("negativa").cast("long").alias("negativas"),
        F.count("*").cast("long").alias("n_resenas"),
    )


def coinciden(a, b) -> bool:
    """True si los dos DataFrames tienen exactamente las mismas filas (multiconjunto)."""
    columnas = a.columns
    b = b.select(*columnas)
    return a.exceptAll(b).limit(1).count() == 0 and b.exceptAll(a).limit(1).count() == 0


def con_tasa(filas: list[dict], min_dias: int) -> list[dict]:
    """Añade tasa anualizada, años-negocio y la marca de mínimo de exposición."""
    salida = []
    for fila in filas:
        tasa = tasa_cierre(fila["cierres"], fila["dias_negocio"])
        salida.append({
            **fila,
            "anios_negocio": round(fila["dias_negocio"] / 365, 2),
            "tasa_cierre": None if tasa is None else round(tasa, 4),
            "cumple_minimo": fila["dias_negocio"] >= min_dias,
        })
    return salida
