"""Consultas de streaming y supervivencia sobre las colecciones de la Entrega 2."""
from time import perf_counter
from datetime import datetime
from flask import Blueprint, current_app, jsonify, request
from .analitica import kaplan_meier
from .rutas import _respuesta, serializar
from . import config
from .validacion import ErrorValidacion, categoria, entero, poligono, punto

bp = Blueprint('live', __name__)


def db():
    return current_app.config['DB']


def filtro_espacial(campo='location'):
    if request.method == 'POST':
        return {campo: {'$geoWithin': {'$geometry': poligono(request.get_json(silent=True))}}}, entero(request.args.get('limit', 100), 'limit', minimo=1, maximo=1000)
    lat, lon, radio, limit = punto(request.args)
    return {campo: {'$near': {'$geometry': {'type': 'Point', 'coordinates': [lon, lat]}, '$maxDistance': radio}}}, limit


@bp.get('/live/hotspots')
def hotspots():
    inicio = perf_counter()
    filtro, limit = filtro_espacial('centro')
    filtro['hotspot'] = True
    ventana = request.args.get('ventana')
    if ventana:
        try:
            fecha = datetime.fromisoformat(ventana)
            if fecha.tzinfo:
                raise ValueError()
        except ValueError:
            raise ErrorValidacion('ventana debe ser una fecha ISO sin zona horaria (UTC).')
        filtro['inicio'] = {'$lte': fecha}
        filtro['fin'] = {'$gt': fecha}
    return _respuesta(list(db().live_windows.find(filtro).limit(limit)), {'ventana': ventana}, inicio)


@bp.route('/alerts', methods=['GET', 'POST'])
def alerts():
    inicio = perf_counter()
    filtro, limit = filtro_espacial()
    filtro['activa'] = True
    return _respuesta(list(db().alerts.find(filtro).limit(limit)), {}, inicio)


@bp.get('/risk/near')
def risk_near():
    inicio = perf_counter()
    filtro, limit = filtro_espacial()
    return _respuesta(list(db().risk_scores.find(filtro).limit(limit)), {}, inicio)


@bp.route('/survival/<path:nombre>', methods=['GET', 'POST'])
def survival(nombre):
    nombre = categoria(nombre)
    filtro = {'categoria_principal': nombre}
    if request.method == 'POST':
        filtro['location'] = {'$geoWithin': {'$geometry': poligono(request.get_json(silent=True))}}
    edad = entero(request.args.get('edad_previa_dias', 0), 'edad_previa_dias', minimo=0, maximo=36500)
    # Limita trabajo por petición, sin truncar silenciosamente la curva.
    negocios = list(db()[config.NEGOCIOS_COLLECTION].find(filtro, {'primera_resena': 1, 'ultima_resena': 1, 'fecha_corte': 1, 'evento': 1}).limit(50001))
    if len(negocios) > 50000:
        raise ErrorValidacion('Más de 50.000 negocios: acota la zona con un polígono.')
    resultado = kaplan_meier(negocios, edad)
    return jsonify(categoria=nombre, muestra_pequena=len(negocios) < 30, **serializar(resultado))


@bp.get('/live/windows')
def windows():
    inicio = perf_counter()
    filtro, limit = filtro_espacial('centro')
    return _respuesta(list(db().live_windows.find(filtro).limit(limit)), {}, inicio)
