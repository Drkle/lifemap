from app.consultas import filtro_near, filtro_within, pipeline_zona


def test_pipeline_zona_calcula_tasa_en_mongo():
    p = pipeline_zona(27.95, -82.45, 1000)
    assert list(p[0]) == ["$geoNear"]
    assert p[0]["$geoNear"]["near"] == {"type": "Point", "coordinates": [-82.45, 27.95]}
    assert "query" not in p[0]["$geoNear"]
    tasa = p[2]["$project"]["tasa_cierre"]
    assert tasa["$cond"][1]["$multiply"][1] == 100


def test_pipeline_zona_con_categoria():
    p = pipeline_zona(1, 2, 3, "Pizza")
    assert p[0]["$geoNear"]["query"] == {"categoria_principal": "Pizza"}
    assert p[1]["$group"]["_id"] is None


def test_filtros_orden_lon_lat():
    assert filtro_near(10, 20, 5)["location"]["$near"]["$geometry"]["coordinates"] == [20, 10]
    assert filtro_within({"type": "Polygon", "coordinates": []})["location"]["$geoWithin"]
