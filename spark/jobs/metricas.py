"""Métricas de clasificación a partir de una matriz de confusión (sin dependencias de Spark)."""

from __future__ import annotations

NOMBRES = {0: "negativo", 1: "neutral", 2: "positivo"}


def matriz(conteos: list[tuple[int, int, int]], clases=(0, 1, 2)) -> list[list[int]]:
    """conteos: (real, predicha, n). Devuelve M[real][predicha]."""
    indice = {c: i for i, c in enumerate(clases)}
    m = [[0] * len(clases) for _ in clases]
    for real, predicha, n in conteos:
        m[indice[int(real)]][indice[int(predicha)]] += int(n)
    return m


def desde_confusion(m: list[list[int]], clases=(0, 1, 2)) -> dict:
    total = sum(sum(fila) for fila in m)
    por_clase = {}
    f1s, soportes = [], []
    for i, clase in enumerate(clases):
        tp = m[i][i]
        predichos = sum(m[r][i] for r in range(len(clases)))
        reales = sum(m[i])
        precision = tp / predichos if predichos else 0.0
        recall = tp / reales if reales else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        por_clase[NOMBRES.get(clase, str(clase))] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "soporte": reales,
        }
        f1s.append(f1)
        soportes.append(reales)
    aciertos = sum(m[i][i] for i in range(len(clases)))
    return {
        "accuracy": round(aciertos / total, 4) if total else 0.0,
        "f1_macro": round(sum(f1s) / len(f1s), 4),
        "f1_ponderado": round(sum(f * s for f, s in zip(f1s, soportes)) / total, 4) if total else 0.0,
        "por_clase": por_clase,
        "matriz_confusion": {"filas_reales_columnas_predichas": [NOMBRES.get(c, str(c)) for c in clases], "valores": m},
        "total": total,
    }
