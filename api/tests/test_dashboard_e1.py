def test_dashboard_e1_se_abre_sin_streaming(client):
    r=client.get('/dashboard/entrega1')
    assert r.status_code==200
    assert b'/businesses/near?' in r.data
    assert b'/businesses/within?' in r.data
    assert b'/live/hotspots' not in r.data
    assert b'Resumen completo del radio' in r.data
