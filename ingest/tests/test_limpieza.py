from datetime import datetime

import pandas as pd
import pytest

import geohash
import limpieza


def _negocios():
    return pd.DataFrame(
        [
            # válido
            dict(business_id="a", name="Pizza A", city="Tampa", state="FL", latitude=27.95, longitude=-82.45,
                 stars=4.0, review_count=10, is_open=1, categories="Restaurants, Pizza, Italian"),
            # N1 coordenadas nulas
            dict(business_id="b", name="B", city="Tampa", state="FL", latitude=None, longitude=-82.45,
                 stars=4.0, review_count=1, is_open=1, categories="Restaurants"),
            # N2 (0, 0)
            dict(business_id="c", name="C", city="Tampa", state="FL", latitude=0, longitude=0,
                 stars=4.0, review_count=1, is_open=1, categories="Restaurants"),
            # N3 otro estado
            dict(business_id="d", name="D", city="Philadelphia", state="PA", latitude=39.95, longitude=-75.16,
                 stars=4.0, review_count=1, is_open=1, categories="Restaurants"),
            # N4 sin la familia
            dict(business_id="e", name="E", city="Tampa", state="FL", latitude=27.95, longitude=-82.45,
                 stars=4.0, review_count=1, is_open=1, categories="Shopping, Books"),
            # N5 is_open inválido
            dict(business_id="f", name="F", city="Tampa", state="FL", latitude=27.95, longitude=-82.45,
                 stars=4.0, review_count=1, is_open=7, categories="Restaurants"),
            # N6 duplicado de "a"
            dict(business_id="a", name="Pizza A", city="Tampa", state="FL", latitude=27.95, longitude=-82.45,
                 stars=4.0, review_count=10, is_open=1, categories="Restaurants, Pizza"),
            # válido, cerrado, solo categorías genéricas
            dict(business_id="g", name="G", city="Tampa", state="fl", latitude=27.96, longitude=-82.46,
                 stars=2.5, review_count=3, is_open=0, categories="Food, Restaurants"),
        ]
    )


def test_limpiar_negocios_cuenta_cada_regla():
    limpio, reporte = limpieza.limpiar_negocios(_negocios(), estados=["FL"], familia="Restaurants")
    assert reporte["total_inicial"] == 8
    for regla in ("N1_coord_nulas", "N2_coord_fuera_rango", "N3_fuera_area", "N4_sin_categoria",
                  "N5_is_open_invalido", "N6_duplicado"):
        assert reporte[regla] == 1, regla
    assert reporte["total_final"] == 2
    assert list(limpio["business_id"]) == ["a", "g"]
    assert list(limpio["categoria_principal"]) == ["Pizza", "Restaurants"]
    assert limpio.loc[0, "geohash"] == geohash.encode(27.95, -82.45, 6)


def test_caja_opcional_filtra_por_coordenadas():
    limpio, reporte = limpieza.limpiar_negocios(
        _negocios(), estados=["FL"], familia="Restaurants", caja=(27.955, 28.0, -82.5, -82.4)
    )
    assert list(limpio["business_id"]) == ["g"]
    assert reporte["N3_fuera_area"] == 5  # PA + las 4 filas en lat 27.95


def _resenas():
    return pd.DataFrame(
        [
            dict(review_id="r1", business_id="a", stars=5, text="Great pizza", date="2019-01-01 10:00:00"),
            dict(review_id="r2", business_id="a", stars=1, text="Awful", date="2020-01-01 10:00:00"),
            dict(review_id="r3", business_id="a", stars=3, text="Ok", date="2019-06-01 10:00:00"),
            dict(review_id="r4", business_id="zzz", stars=5, text="Otro lugar", date="2022-01-19 10:00:00"),
            dict(review_id="r5", business_id="a", stars=4, text="   ", date="2019-01-02 10:00:00"),
            dict(review_id="r6", business_id="a", stars=9, text="raro", date="2019-01-02 10:00:00"),
            dict(review_id="r7", business_id="a", stars=4, text="sin fecha", date="no-es-fecha"),
            dict(review_id="r8", business_id="g", stars=2, text="Bad", date="2018-03-01 08:00:00"),
        ]
    )


def test_limpiar_resenas_reglas_y_etiquetas():
    limpio, reporte = limpieza.limpiar_resenas(_resenas(), {"a", "g"})
    assert reporte["R1_negocio_no_valido"] == 1
    assert reporte["R2_texto_vacio"] == 1
    assert reporte["R3_estrellas_invalidas"] == 1
    assert reporte["R4_fecha_invalida"] == 1
    assert reporte["total_final"] == 4
    # La fecha de corte se mide antes de filtrar: r4 es de otra área pero cuenta.
    assert reporte["fecha_max"] == pd.Timestamp("2022-01-19 10:00:00")
    etiquetas = dict(zip(limpio["review_id"], limpio["etiqueta"]))
    assert etiquetas == {"r1": 2, "r2": 0, "r3": 1, "r8": 0}
    assert reporte["por_etiqueta"] == {"positivo": 1, "negativo": 2, "neutral": 1}


def test_vida_evento_y_censura():
    negocios, _ = limpieza.limpiar_negocios(_negocios(), estados=["FL"], familia="Restaurants")
    limpio, _ = limpieza.limpiar_resenas(_resenas(), {"a", "g"})
    agregados = limpieza.combinar_agregados(
        [limpieza.agregar_por_negocio(limpio.iloc[:2]), limpieza.agregar_por_negocio(limpio.iloc[2:])]
    )
    corte = datetime(2022, 1, 19)
    vida, sin_resenas = limpieza.construir_vida(negocios, agregados, corte)
    assert sin_resenas == 0
    a = vida.set_index("business_id").loc["a"]
    assert a["n_resenas"] == 3
    assert a["dias_negocio"] == 366  # 2019-01-01 a 2020-01-01, ambos días incluidos
    assert a["evento"] == 0 and bool(a["censurado"]) is True
    assert a["pct_negativas"] == pytest.approx(100 / 3)
    g = vida.set_index("business_id").loc["g"]
    assert g["dias_negocio"] == 1 and g["evento"] == 1 and bool(g["censurado"]) is False

    doc = limpieza.documento_negocio(vida.iloc[0].to_dict(), corte)
    assert doc["location"] == {"type": "Point", "coordinates": [-82.45, 27.95]}
    assert doc["_id"] == "a"


def test_negocio_sin_resenas_se_descarta_n7():
    negocios, _ = limpieza.limpiar_negocios(_negocios(), estados=["FL"], familia="Restaurants")
    limpio, _ = limpieza.limpiar_resenas(_resenas(), {"a"})
    vida, sin_resenas = limpieza.construir_vida(negocios, limpieza.agregar_por_negocio(limpio), datetime(2022, 1, 1))
    assert sin_resenas == 1
    assert list(vida["business_id"]) == ["a"]


def test_geohash_conocido_y_poligono_cerrado():
    # Valor de referencia: geohash de (57.64911, 10.40744) = u4pruydqqvj
    assert geohash.encode(57.64911, 10.40744, 11) == "u4pruydqqvj"
    lat_min, lat_max, lon_min, lon_max = geohash.bbox("u4pruy")
    assert lat_min <= 57.64911 <= lat_max and lon_min <= 10.40744 <= lon_max
    anillo = geohash.poligono("u4pruy")["coordinates"][0]
    assert anillo[0] == anillo[-1] and len(anillo) == 5
